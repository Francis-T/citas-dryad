/**
 * Relay Node Program
 * CITAS Dryad 2017
 * 
 * Dependencies
 *  Libraries
 *    - DS3231 by Adafruit
 *    - RTCLib by Arduino 
 *  Boards
 *    - Arduino SAMD
 *    - Adafruit SAMD
*/

/***********************/
/*      libraries      */
/***********************/
#include <string.h>
#include <stdio.h>
#include <stdint.h>
#include <time.h>

// RTC
#include <Wire.h>
#include "RTClib.h" // DS3231 RTC
#include <RTCZero.h> // Feather internal RTC

// Transmission-related libraries
#include <SPI.h>
#include <RH_RF69.h> // For the feather radio
#include <RH_RF95.h> // For the LoRa 9x
#include <RHMesh.h>
#include <RHReliableDatagram.h>


/***********************/
/*    Var definitions  */
/***********************/
// 434 Frequency for CITAS
#define RF69_FREQ 434.0
#define RF95_FREQ 434.0

// Define Feather and LoRa
#define ARDUINO_SAMD_FEATHER_M0
#define ADAFRUIT_LORA_9X

// who am i? (server address)
#define MY_ADDRESS     90

// Destination addresses
#define DEST_ADDRESS   88               

// Pin definitions for Feather and LoRa
#if defined(ARDUINO_SAMD_FEATHER_M0) // Feather M0 w/Radio
  #define RFM69_CS      8
  #define RFM69_INT     3
  #define RFM69_RST     4
  #define LED           13
#endif

#if defined(ADAFRUIT_LORA_9X) // Adafruit LoRa
  #define RFM95_CS 10
  #define RFM95_RST 9
  #define RFM95_INT 11
#endif

// Status variables
#define STATUS_FAILED     -1
#define STATUS_OK         1
#define STATUS_CONTINUE   2

// Duration and Timeout in Milliseconds
#define IDLE_TIMEOUT      30000
#define CACHING_DURATION  120000
#define TXING_DURATION    30000
#define SLEEP_TIME        15000

/** Note: SLEEP_TIME_SECS is separated here because
 *        the RTC wakeup alarm / timer needs it to
 *        be in seconds instead of millisecs */
#define SLEEP_TIME_SECS   SLEEP_TIME / 1000

/* Battery pin definition */
#define VBATPIN A7

/* Data variable definitions */
#define USE_ARDUINO
#define DEBUG_MODE

#define OFFS_HEADER         0
#define OFFS_PAYLOAD        11
#define OFFS_FOOTER         24

#define LEN_HEADER          11
#define LEN_PAYLOAD_DATA    14
#define LEN_PAYLOAD_STATUS  5

#define PROTO_MAJ_VER       0
#define PROTO_MIN_VER       1

#define TYPE_REQ_UNKNOWN    0
#define TYPE_REQ_STATUS     1
#define TYPE_REQ_DATA       2

/***********************/
/*   Var Declarations  */
/***********************/
// Different possible device states
typedef enum {
  STATE_INACTIVE,
  STATE_UNDEPLOYED,
  STATE_IDLE,
  STATE_ASLEEP,
  STATE_CACHING,
  STATE_TXING,
} eState_t;

// Struct definitions 
typedef struct {
    uint8_t uContentType;
    uint8_t uContentLen;
    uint8_t uMajVer;
    uint8_t uMinVer;
    uint64_t uTimestamp;
    uint8_t aPayload[17];
} tPacket_t;

// Equivalent strings for the different eState_ts
char _stateStr[][12] = {
  "INACTIVE",
  "UNDEPLOYED",
  "IDLE",
  "ASLEEP",
  "CACHING",
  "TXING",
};

typedef struct {
    uint16_t uNodeId;
    uint16_t uPower;
    uint8_t  uDeploymentState;
    uint8_t  uStatusCode;
} tStatusPayload_t;

typedef struct {
    uint16_t uNodeId;
    uint16_t uRelayId;
    uint16_t uPH;
    uint16_t uConductivity;
    uint16_t uLight;
    uint16_t uTempAir;
    uint16_t uTempSoil;
    uint16_t uHumidity;
    uint16_t uMoisture;
    uint16_t uReserved;
} tDataPayload_t;

typedef int (*fHandlerFunc_t)(void* pPayload, uint8_t* pRecvBuf, uint16_t uRecvLen);

typedef struct {
    uint8_t uContentType;
    fHandlerFunc_t fHandler;
} tDataHandler_t;

int comm_parseStatusPayload(void*, uint8_t*, uint16_t);
int comm_parseDataPayload(void*, uint8_t*, uint16_t);

tDataHandler_t aDataHdlTbl[] = {
    { TYPE_REQ_STATUS, comm_parseStatusPayload },
    { TYPE_REQ_DATA, comm_parseDataPayload }
};

/*************************/
/* Function Declarations */
/*************************/
void setup();
void loop();
int proc_hdlInactive();
int proc_hdlUndeployed();
int proc_hdlIdle();
int proc_hdlAsleep();
int proc_hdlCaching();
int proc_hdlTxing();
int cfg_processSerialInput();

int comm_sendStatusPacket();

void state_set(eState_t newState);
eState_t state_get();
void utl_hdlInterrupt();

void rtc_init();

int radio_init(void);
int radio_recv();

int lora_init(void);
int lora_send(char* buf, int len);
float utl_measureBatt();

/* Global Variable Declarations */
RTCZero _radioRtc; // Create Feather / radio RTC object
RTC_DS3231 _rtc; // Create global RTC object
DateTime _now = NULL;

RH_RF69 _rf69(RFM69_CS, RFM69_INT);              
RH_RF95 _rf95(RFM95_CS, RFM95_INT);
RHReliableDatagram  _rf69_manager(_rf69, MY_ADDRESS);  /* Class to manage message delivery and 
                                                      * receipt, using the driver declared above */
eState_t _prevState = STATE_INACTIVE;
eState_t _state = STATE_INACTIVE;

int _iPacketNum = 0;
float _fBatt = 0.0;

long _lastIdleTime = 0;
long _lastCacheTime = 0;
long _lastTxingTime = 0;
bool _workDone = false;   /* This flag could be for data collection, retransmission, etc. */

uint8_t _recvBuf[RH_RF69_MAX_MESSAGE_LEN];
uint8_t _sendBuf[RH_RF69_MAX_MESSAGE_LEN];

tPacket_t   _tInputPacket;
tPacket_t   _tDecodedPacket;
tStatusPayload_t _tStatusPayload;
tDataPayload_t _tDataPayload;

/**
 * @desc    Setup function implementing initialization of rtc, radio, lora, and 
 *          serial
 * @return  void
 */
void setup() {
  while (!Serial) { delay(1); }

  // Start Serial
  Serial.begin(115200);

  // Assign LED pin mode to Output
  pinMode(LED, OUTPUT);
  
  // Initialize RTC 
  rtc_init();
  
  // Setup Radio
  pinMode(RFM69_RST, OUTPUT);
  digitalWrite(RFM69_RST, LOW);

  // Setup LoRa 
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  // Call initialization for radio and lora
  radio_init();
  lora_init();

  // Display addresses
  Serial.print("Self address @"); Serial.println(MY_ADDRESS);
  Serial.print("Dest address @"); Serial.println(DEST_ADDRESS);
  
  return;
}


/**
 * @desc    Main looping function. This also contains the switch statement which launches
 *          different functions depending on the current device state.
 * @return  void
 */
void loop() {
  _now = _rtc.now();
  _fBatt = utl_measureBatt(); 
  
  int iRet = 0;

  // State switch cases
  switch (state_get()) {
    case STATE_INACTIVE:
      iRet = proc_hdlInactive();
      break;
      
    case STATE_UNDEPLOYED:
      iRet = proc_hdlUndeployed();
      break;
      
    case STATE_IDLE:
      iRet = proc_hdlIdle();
      break;
      
    case STATE_ASLEEP:
      iRet = proc_hdlAsleep();
      break;
      
    case STATE_CACHING:
      iRet = proc_hdlCaching();
      break;

    case STATE_TXING:
      iRet = proc_hdlTxing();
      break;
      
    default:
      break;
  }

  // Sanity delay
  delay(10);

  return;
}

/**************************************************/
/**   Processing Functions for each device state **/
/**************************************************/

/**
 * @desc    Handler for the STATE_INACTIVE. We never stay too long in this state since it is
 *          simply a placeholder state that waits for the device to be switched ON.
 * @return  an integer status
 */
int proc_hdlInactive() {
  state_set(STATE_UNDEPLOYED);
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_UNDEPLOYED device state. In this state, the node waits for
 *          the user to properly configure the node before it can be used.
 * @return  an integer status
 */
int proc_hdlUndeployed() {
  /* During the UNDEPLOYED state, we are allowed to send Serial data to the microcontroller
   *  in order to configure it. In the case of the Field Nodes, this can be used to set things
   *  like the node address of the node itself, or the node address of its target node.
   */
  while (!Serial);
  while (Serial.available() == false);

  /* Force the node to be manually configured before it can be used --
   *  we can have an external switch that is checked through digitalRead() 
   *  to allow this configuration process to be skipped when this node has
   *  already been deployed before anyway */
//  if (digitalRead(IS_DEPLOYED_SW) == LOW) {
      while (cfg_processSerialInput() == STATUS_CONTINUE);
        delay(10);
//  }

  state_set(STATE_IDLE);
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_IDLE. A state that simply waits for events to be done.
 * 
 *          If the device enters this state while the 'work' is not yet done (as indicated 
 *          by the _workDone flag), then it immediately transitions to STATE_CACHING instead.
 *          
 *          On the other hand, if we enter this state and we've run out of time (IDLE_TIMEOUT),
 *          then we simply move on to STATE_ASLEEP instead.
 *          
 * @return  an integer status
 */
int proc_hdlIdle() {
  
  digitalWrite(LED, HIGH); // Turn LED on to specify the board is awake
  if ((millis() - _lastIdleTime) > IDLE_TIMEOUT) {
    /* If the time since the device last started idling exceeds the IDLE_TIMEOUT,
     *  then it is time to put the device back to the ASLEEP state for a bit */
    state_set(STATE_ASLEEP);
    
  } else if (_workDone == false) {
    /* Record time before caching */
    _lastCacheTime = millis();
    state_set(STATE_CACHING);
    _workDone = true;
    
  }
  
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_ASLEEP device state. Low power sleep functionality
 *          has ALREADY been incorporated here but has not yet been extensively
 *          tested.
 * @return  an integer status
 */
int proc_hdlAsleep() {  
  /* Set the built-in RTC to wake the device up SLEEP_TIME_SECS from now */
  int iWakeupTime = (_radioRtc.getSeconds() + SLEEP_TIME_SECS) % 60;
  _radioRtc.setAlarmSeconds(iWakeupTime);         // RTC time to wake, currently seconds only
  _radioRtc.enableAlarm(_radioRtc.MATCH_SS);            // Match seconds only
  _radioRtc.attachInterrupt(utl_hdlRtcInterrupt); // Attaches function to be called, currently blank
  delay(50); // Brief delay prior to sleeping not really sure its required
  
  digitalWrite(LED, LOW); // Turn LED off to specify board is asleep
  
  Serial.end();
  USBDevice.detach(); // Safely detach the USB prior to sleeping
  _radioRtc.standbyMode(); // Sleep until next alarm match
  USBDevice.attach(); // Re-attach the USB, audible sound on windows machines

  // Blink(LED, 100, 6); // Blink 6 times with 100ms interval

  /* Re-start the Serial again since we stopped it before detaching */
  Serial.begin(115200);
  Serial.println("After detach");
  delay(10000);

  /* Set the work done flag back to false */
  _workDone = false;

  Serial.println("Before status packet sending");

  if(comm_sendStatusPacket() == STATUS_OK){
    Serial.println("Status Packet Sent!");
  }

  Serial.println("After status packet sending");
  // Record when we last started idling again
  _lastIdleTime = millis();

  // Finally, set the state machine back to STATE_IDLE
  state_set(STATE_IDLE);
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_CACHING device state. 
 * @return  an integer status
 */
int proc_hdlCaching() {
  /* Listen to data broadcasts from sensor node senders for some time */
  Serial.println("Start listening...");
  while(millis() - _lastCacheTime <= CACHING_DURATION){
    if(radio_recv() == STATUS_OK) {
      Serial.println("Got a message.");
      break; // Break out of while loop once data is received
    }
    delay(200); // Sanity delay
  }
  
  /* Record time before txing */
  _lastTxingTime = millis();
  
  /* Set the state machine to STATE_Txing */
  state_set(STATE_TXING);
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_TXING device state.
 * @return  an integer status
 */
int proc_hdlTxing() {
  /* Transmit cached data to destination node */
  // TODO Go through and empty out cached data

  // Clear the buffer for receiving status data
  memset(&_tDecodedPacket, 0, sizeof(_tDecodedPacket));
  memset(&_sendBuf, '\0', sizeof(_sendBuf)/sizeof(_sendBuf[0]));

  // Parse and encode timestamp to the received packet 
  comm_parseHeader(&_tDecodedPacket, _recvBuf, 9);
  _tDecodedPacket.uTimestamp = _now.unixtime();
  comm_writePacket(_sendBuf, &_tDecodedPacket);
  
  while(millis() - _lastTxingTime <= TXING_DURATION){
    if(lora_send((char*)_sendBuf, sizeof(_sendBuf)) == STATUS_OK){
      Serial.println("Message sent!");
      break;
    }
  }

  /* Finally, set the state machine back to STATE_IDLE */
  state_set(STATE_IDLE);
  return STATUS_OK;
}

/*******************************/
/**   Configuration Functions **/
/*******************************/
/**
 * @desc    Processes Serial input from the user. This allows the node's parameters
 *          to be configured on the field through a Serial interface. This can, for
 *          example, be used to configure the node address for this particular node.
 * @return  an integer status
 */
int cfg_processSerialInput() {
  char aBuf[64];
  
  /* Clear the Serial input buffer */
  memset(aBuf, 0, sizeof(aBuf));

  /* Attempt to read data from the buffer */
  int iBytesRead = 0;
  while (Serial.available()) {
    aBuf[iBytesRead] = Serial.read();
    iBytesRead += 1;
    
    if (iBytesRead >= sizeof(aBuf)) {
      break;
    }
  }

  if (iBytesRead <= 0) {
    return STATUS_CONTINUE;
  }

  Serial.print("Received: ");
  Serial.println(aBuf);

  if ( strncmp(aBuf, "END", 3) == 0) {
    Serial.println("Accepted END");
    return STATUS_OK;
  } else if ( strncmp(aBuf, "SET NODE ADDR ", 14) == 0 ) {
    Serial.print("Node address set to ");
    Serial.println((int)(aBuf[14]));
    
  } else if ( strncmp(aBuf, "SET RELAY ADDR ", 15) == 0 ) {
    Serial.print("Relay address set to ");
    Serial.println((int)(aBuf[15]));
    
  }
  
  return STATUS_CONTINUE;
}

/******************************/
/**   Device State Functions **/
/******************************/
/**
 * @desc    Sets the state of the device
 * @return  void
 */
void state_set(eState_t newState) {
  if (newState != _state) {
    _prevState = _state;
    Serial.print("State: ");
    Serial.println(_stateStr[(int)(newState)]);
  }
  _state = newState;
  return;
}

/**
 * @desc    Gets the state of the device
 * @return  an eState_t, indicating the state of the device
 */
eState_t state_get() {
  return _state;
}

/******************************/
/**   RTC Functions          **/
/******************************/
void rtc_init() {
    /* Start the built-in RTC */
  _rtc.begin();
  _radioRtc.begin(); // Start the RTC in 24hr mode

  if (_rtc.lostPower()) {
    Serial.println("RTC lost power, lets set the time!");
    // following line sets the RTC to the date & time this sketch was compiled
    _rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
}

/******************************/
/**   Radio Functions        **/
/******************************/
 
int radio_init() {
  Serial.println("Feather Radio Initialization...");
  
  /* Reset the RFM69 radio (?) */
  digitalWrite(RFM69_RST, HIGH);
  delay(10);
  digitalWrite(RFM69_RST, LOW);
  delay(10);

  /* Initialize RF69 Manager */
  if (!_rf69_manager.init()) {
    Serial.println("RFM69 radio init failed");
    while (1);
  }
  _rf69_manager.setTimeout(2000);
  
  Serial.println("RFM69 radio init OK!");
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM (for low power module)
  // No encryptiond
  if (!_rf69.setFrequency(RF69_FREQ)) {
    Serial.println("setFrequency failed");
  }

  // If you are using a high power RF69 eg RFM69HW, you *must* set a Tx power with the
  // ishighpowermodule flag set like this:
  _rf69.setTxPower(20, true);  // range from 14-20 for power, 2nd arg must be true for 69HCW

  // The encryption key has to be the same as the one in the server
  uint8_t key[] = { 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};
  _rf69.setEncryptionKey(key);
  Serial.print("RFM69 radio @");  Serial.print((int)RF69_FREQ);  Serial.println(" MHz");
  return STATUS_OK;
}


int radio_recv(){
  uint8_t data[] = "And hello back to you";
  if (_rf69_manager.available()) {
    // Wait for a message addressed to us from the client
    uint8_t len = sizeof(_recvBuf);
    uint8_t from;
    if (_rf69_manager.recvfromAck(_recvBuf, &len, &from)) {
      _recvBuf[len] = 0;
      
      Serial.print("Got packet from #"); Serial.print(from);
      Serial.print(" [RSSI :");
      Serial.print(_rf69.lastRssi());
      Serial.print("] : ");
      Serial.println((char*)_recvBuf);
      Blink(LED, 40, 3); //blink LED 3 times, 40ms between blinks

      // Send a reply back to the originator client
      if (!_rf69_manager.sendtoWait(data, sizeof(data), from))
        Serial.println("Sending failed (no ack)");

      return STATUS_OK;
    }
  }
  return STATUS_FAILED;
}

/***********************/
/**   LoRa Functions  **/
/***********************/
int lora_init(){
  Serial.println("Arduino LoRa Initialization...");
  
  // manual reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);
 
  while (!_rf95.init()) {
    Serial.println("LoRa radio init failed");
    while (1);
  }
  Serial.println("LoRa radio init OK!");
 
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!_rf95.setFrequency(RF95_FREQ)) {
    Serial.println("setFrequency failed");
    while (1);
  }
  Serial.print("RM95 radio @"); Serial.println(RF95_FREQ);
  
  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
 
  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
  // you can set transmitter powers from 5 to 23 dBm:
  _rf95.setTxPower(23, false); 

  return STATUS_OK;
}

int lora_send(char* buf, int len){
  Serial.println("Sending message.."); delay(10);
  _rf95.send((uint8_t *)buf, len);
  
  Serial.println("Waiting for packet to complete..."); delay(10);
  _rf95.waitPacketSent();

  return STATUS_OK;
}



/***********************/
/**   Dummy Functions **/
/***********************/

float utl_measureBatt() {
  float batt = analogRead(VBATPIN);
  batt *= 2; // we divided by 2, so multiply back
  batt *= 3.3; // Multiply by 3.3V, our reference voltage
  batt /= 1024; // convert to voltage
  return batt;
}

void utl_hdlRtcInterrupt() // Do something when interrupt called
{
  
}

void Blink(byte PIN, byte DELAY_MS, byte loops) {
  for (byte i=0; i<loops; i++)  {
    digitalWrite(PIN,HIGH);
    delay(DELAY_MS);
    digitalWrite(PIN,LOW);
    delay(DELAY_MS);
  }
}

/***********************/
/** Payload Functions **/
/***********************/
int comm_createStatusPayload( uint8_t* pPayloadBuf, tStatusPayload_t* pData )
{
    /* TODO Input checking */
    pPayloadBuf[ 0]  = (uint8_t)((pData->uNodeId >> 8) & 0xFF );
    pPayloadBuf[ 1]  = (uint8_t)( pData->uNodeId & 0xFF );
    pPayloadBuf[ 2]  = (uint8_t)((pData->uPower >> 2) & 0xFF );
    pPayloadBuf[ 3]  = (uint8_t)((pData->uPower & 0x03) << 6 );
    pPayloadBuf[ 3] |= (uint8_t)((pData->uDeploymentState & 0x01) << 5 );
    pPayloadBuf[ 4]  = (uint8_t)( pData->uStatusCode );

    return STATUS_OK;
}

int comm_createDataPayload( uint8_t* pPayloadBuf, tDataPayload_t* pData )
{
    /* TODO Input checking */
    pPayloadBuf[ 0]  = (uint8_t)((pData->uNodeId >> 8) & 0xFF );
    pPayloadBuf[ 1]  = (uint8_t)( pData->uNodeId & 0xFF );
    pPayloadBuf[ 2]  = (uint8_t)((pData->uRelayId >> 8) & 0xFF );
    pPayloadBuf[ 3]  = (uint8_t)( pData->uRelayId & 0xFF );

    pPayloadBuf[ 4]  = (uint8_t)((pData->uPH >> 2) & 0xFF);
    pPayloadBuf[ 5]  = (uint8_t)((pData->uPH << 6) & 0xC0);
    pPayloadBuf[ 5] |= (uint8_t)((pData->uConductivity >> 4) & 0x3F);
    pPayloadBuf[ 6]  = (uint8_t)((pData->uConductivity << 4) & 0xF0);
    pPayloadBuf[ 6] |= (uint8_t)((pData->uLight >> 6) & 0x0F);
    pPayloadBuf[ 7]  = (uint8_t)((pData->uLight << 2) & 0xFC);
    pPayloadBuf[ 7] |= (uint8_t)((pData->uTempAir >> 8) & 0x03);
    pPayloadBuf[ 8]  = (uint8_t)((pData->uTempAir) & 0xFF);


    pPayloadBuf[ 9]  = (uint8_t)((pData->uHumidity >> 2) & 0xFF);
    pPayloadBuf[10]  = (uint8_t)((pData->uHumidity << 6) & 0xC0);
    pPayloadBuf[10] |= (uint8_t)((pData->uTempSoil >> 4) & 0x3F);
    pPayloadBuf[11]  = (uint8_t)((pData->uTempSoil << 4) & 0xF0);
    pPayloadBuf[11] |= (uint8_t)((pData->uMoisture >> 6) & 0x0F);
    pPayloadBuf[12]  = (uint8_t)((pData->uMoisture << 2) & 0xFC);
    pPayloadBuf[12] |= (uint8_t)((pData->uReserved >> 8) & 0x03);
    pPayloadBuf[13]  = (uint8_t)((pData->uReserved) & 0xFF);

    return STATUS_OK;
}

int comm_writeHeader( uint8_t* pPacketBuf, tPacket_t* pData )
{
    /* TODO Input checking */
    pPacketBuf[OFFS_HEADER]      = (uint8_t)( 0xC << 4 );
    pPacketBuf[OFFS_HEADER]     |= (uint8_t)((pData->uContentType >> 2) & 0x0F );
    pPacketBuf[OFFS_HEADER + 1]  = (uint8_t)((pData->uContentType << 6) & 0xC0 );
    pPacketBuf[OFFS_HEADER + 1] |= (uint8_t)( pData->uContentLen & 0x3F );
    pPacketBuf[OFFS_HEADER + 2]  = (uint8_t)((pData->uMajVer << 4) & 0xF0 );
    pPacketBuf[OFFS_HEADER + 2] |= (uint8_t)( pData->uMinVer & 0x0F );
    memcpy(&pPacketBuf[OFFS_HEADER + 3], &pData->uTimestamp, 8 );

    return STATUS_OK;
}

int comm_writePayload( uint8_t* pPacketBuf, tPacket_t* pData )
{
    memcpy(&pPacketBuf[OFFS_PAYLOAD], pData->aPayload, pData->uContentLen );
    return STATUS_OK;
}

int comm_writeFooter( uint8_t* pPacketBuf, uint16_t uLen )
{
    int iSum = 0;
    for (uint16_t i = 0; i < uLen; i++)
    {
        iSum += pPacketBuf[i];
    }

    pPacketBuf[uLen]  = (uint8_t)((iSum << 4) & 0x000000F0);
    pPacketBuf[uLen] |= (uint8_t)(0x03);

    return STATUS_OK;
}

int comm_writePacket( uint8_t* pPacketBuf, tPacket_t* pPacket )
{
    comm_writeHeader(pPacketBuf, pPacket);
    comm_writePayload(pPacketBuf, pPacket);
    comm_writeFooter(pPacketBuf, (pPacket->uContentLen + LEN_HEADER));

    return STATUS_OK;
}

int comm_parseHeader( tPacket_t* pPacketData, uint8_t* pRecvBuf, uint16_t uRecvLen )
{
    pPacketData->uContentType = ((pRecvBuf[OFFS_HEADER] & 0x0F) << 2) |
                                ((pRecvBuf[OFFS_HEADER + 1] & 0xC0) >> 6);
    pPacketData->uContentLen  = (pRecvBuf[OFFS_HEADER + 1] & 0x3F);
    pPacketData->uMajVer      = ((pRecvBuf[OFFS_HEADER + 2] & 0xF0) >> 4);
    pPacketData->uMinVer      = (pRecvBuf[OFFS_HEADER + 2] & 0x0f);
    
    memcpy(&pPacketData->uTimestamp, &pRecvBuf[OFFS_HEADER + 3], sizeof(pPacketData->uTimestamp));

    memset(pPacketData->aPayload, 0, sizeof(pPacketData->aPayload));
    memcpy(pPacketData->aPayload, &pRecvBuf[OFFS_PAYLOAD], pPacketData->uContentLen);

    return STATUS_OK;
}

int comm_parseDataPayload( void* pPayload, uint8_t* pPayloadBuf, uint16_t uRecvLen)
{
    tDataPayload_t* pDataPayload = (tDataPayload_t*) pPayload;

    pDataPayload->uNodeId = ((pPayloadBuf[0] & 0xFF) << 8) |
                            (pPayloadBuf[1] & 0xFF);
    pDataPayload->uRelayId = ((pPayloadBuf[2] & 0xFF) << 8) |
                              (pPayloadBuf[3] & 0xFF);
    pDataPayload->uPH = (pPayloadBuf[4] << 2) | 
                        ((pPayloadBuf[5] & 0xC0) >> 6);
    pDataPayload->uConductivity = ((pPayloadBuf[5] & 0x3F) << 4) | 
                                  ((pPayloadBuf[6] & 0xF0) >> 4);
    pDataPayload->uLight = ((pPayloadBuf[6] & 0x0F) << 6) | 
                            ((pPayloadBuf[7] & 0xFC) >> 2);
    pDataPayload->uTempAir = ((pPayloadBuf[7] & 0x0F) << 6) | 
                              ((pPayloadBuf[8] & 0xFC) >> 2);
    pDataPayload->uHumidity = (pPayloadBuf[9] << 2) | 
                              ((pPayloadBuf[10] & 0xC0) >> 6);
    pDataPayload->uTempSoil = ((pPayloadBuf[10] & 0x3F) << 4) | 
                              ((pPayloadBuf[11] & 0xF0) >> 4);
    pDataPayload->uMoisture = ((pPayloadBuf[11] & 0x0F) << 6) | 
                              ((pPayloadBuf[12] & 0xFC) >> 2);
    pDataPayload->uReserved = ((pPayloadBuf[12] & 0x0F) << 6) | 
                              ((pPayloadBuf[13] & 0xFC) >> 2);

    return STATUS_OK;
}

int comm_parseStatusPayload( void* pPayload, uint8_t* pRecvBuf, uint16_t uRecvLen )
{
    tStatusPayload_t* pStatusPayload = (tStatusPayload_t*) pPayload;

    pStatusPayload->uNodeId = ((pRecvBuf[0] & 0xFF) << 8) |
                               (pRecvBuf[1] & 0xFF);
    pStatusPayload->uPower = ((pRecvBuf[2] & 0xFF) << 2) | 
                             ((pRecvBuf[3] & 0x03) >> 6);
    pStatusPayload->uDeploymentState = ((pRecvBuf[3] >> 5) & 0x01);
    pStatusPayload->uStatusCode = pRecvBuf[4];

    return STATUS_OK;
}

int comm_setPacketHeader(){
  memset(&_tInputPacket, 0, sizeof(_tInputPacket));

  // Create the packet header
  _tInputPacket.uContentType = TYPE_REQ_UNKNOWN;
  _tInputPacket.uContentLen  = LEN_PAYLOAD_STATUS;
  _tInputPacket.uMajVer      = PROTO_MAJ_VER;
  _tInputPacket.uMinVer      = PROTO_MIN_VER;
  _tInputPacket.uTimestamp   = _now.unixtime();

  return STATUS_OK;

}

int comm_sendStatusPacket(){
  // Clear and create the packet
  memset(_sendBuf, '\0', sizeof(_sendBuf)/sizeof(_sendBuf[0]));
  memset(&_tStatusPayload, 0, sizeof(_tStatusPayload));

  if(comm_setPacketHeader() != STATUS_OK){
    return STATUS_FAILED;
  }

  // Create the status payload
  _tStatusPayload.uNodeId          = MY_ADDRESS;
  _tStatusPayload.uPower           = _fBatt;
  _tStatusPayload.uDeploymentState = 1;
  _tStatusPayload.uStatusCode      = 0xFF;

  // Creating and writing status payload to input packet
  comm_createStatusPayload(_tInputPacket.aPayload, &_tStatusPayload);
  comm_writePacket(_sendBuf, &_tInputPacket);

  // Send the packet
  if(lora_send((char *)_sendBuf, sizeof(_sendBuf)) == STATUS_OK){
    return STATUS_OK;
  }

  return STATUS_FAILED;
}
