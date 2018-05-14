/**
 * Relay Node Program
 * CITAS Dryad 2017
 * 
 * Dependencies
 *  Libraries
 *    - RTCLib by Adafruit 
 *    - RadioHead
 *    - RTCZero
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

// Debugging settings
#define DEBUG_MSGS_ON
#if defined(DEBUG_MSGS_ON)
#define DBG_PRINT(x)    Serial.print(x)
#define DBG_PRINTLN(x)  Serial.println(x)

#else
#define DBG_PRINT(x)    NULL;
#define DBG_PRINTLN(x)  NULL;

#endif


/***********************/
/*    Var definitions  */
/***********************/
// Identifiers
#define ID_REL_NODE       90
#define ID_AGG_NODE       92

// 434 Frequency for CITAS
#define RF69_FREQ 434.0
#define RF95_FREQ 434.0

// Define Feather and LoRa
#define ARDUINO_SAMD_FEATHER_M0
#define ADAFRUIT_LORA_9X

// who am i? (server address)
#define MY_ADDRESS     ID_REL_NODE

// Destination addresses
#define DEST_ADDRESS   ID_AGG_NODE               

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
#define IDLE_TIMEOUT      10000
#define LISTEN_TIMEOUT    5000
#define TRANSMIT_TIMEOUT  5000
#define LIS_TX_DURATION   30000
#define SLEEP_TIME        20000

/** Note: SLEEP_TIME_SECS is separated here because
 *        the RTC wakeup alarm / timer needs it to
 *        be in seconds instead of millisecs */
#define SLEEP_TIME_SECS   SLEEP_TIME / 1000

/* Battery pin definition */
#define PIN_VBAT A7

/* Data variable definitions */
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
  STATE_LISTEN,
  STATE_TRANSMIT,
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
  "LISTEN",
  "TRANSMIT",
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
int proc_hdlListen();
int proc_hdlTransmit();
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
int utl_measureBatt();

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
int _iBatt = 0.0;

long _lastIdleTime = 0;
long _lastListenTime = 0;
long _lastTransmitTime = 0;
long _lisTxStartTime = 0;
bool _workDone = false;   /* This flag could be for data collection, retransmission, etc. */

uint8_t _recvBuf[RH_RF69_MAX_MESSAGE_LEN];
uint8_t _sendBuf[RH_RF69_MAX_MESSAGE_LEN];

bool _isDataAvailable = false; // This flag will be used as a condition for transmitting

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
  DBG_PRINT("Self address @"); DBG_PRINTLN(MY_ADDRESS);
  DBG_PRINT("Dest address @"); DBG_PRINTLN(DEST_ADDRESS);
  
  return;
}

/**
 * @desc    Main looping function. This also contains the switch statement which launches
 *          different functions depending on the current device state.
 * @return  void
 */
void loop() {
  _now = _rtc.now();
  _iBatt = utl_measureBatt(); 
  
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
      
    case STATE_LISTEN:
      iRet = proc_hdlListen();
      break;

    case STATE_TRANSMIT:
      iRet = proc_hdlTransmit();
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
//  while (!Serial);
//  while (Serial.available() == false);

  /* Force the node to be manually configured before it can be used --
   *  we can have an external switch that is checked through digitalRead() 
   *  to allow this configuration process to be skipped when this node has
   *  already been deployed before anyway */
//  if (digitalRead(IS_DEPLOYED_SW) == LOW) {
//      while (cfg_processSerialInput() == STATUS_CONTINUE);
        DBG_PRINTLN("==> [SYS] Starting processes.");
//        delay(10);
//  }
  _lastIdleTime = millis();
  state_set(STATE_IDLE);
  
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_IDLE. A state that simply waits for events to be done.
 * 
 *          If the device enters this state while the 'work' is not yet done (as indicated 
 *          by the _workDone flag), then it immediately transitions to STATE_LISTEN instead.
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
    // Send status packet
    if(comm_sendStatusPacket() == STATUS_OK){
      DBG_PRINTLN("==> [TX] Sent status packet.");
    }
    else{
      DBG_PRINTLN("==> [TX] Failed sensor status sending.");
    }
    /* Record time before LISTEN */
    _lastListenTime = millis();
    _lisTxStartTime = millis();
    state_set(STATE_LISTEN);
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
  _radioRtc.attachInterrupt(utl_hdlInterrupt); // Attaches function to be called, currently blank
  delay(50); // Brief delay prior to sleeping not really sure its required
  
  digitalWrite(LED, LOW); // Turn LED off to specify board is asleep
  
  Serial.end();
  USBDevice.detach(); // Safely detach the USB prior to sleeping
  _radioRtc.standbyMode(); // Sleep until next alarm match
  USBDevice.attach(); // Re-attach the USB, audible sound on windows machines
  
  /* Re-start the Serial again since we stopped it before detaching */
  Serial.begin(115200);

  /* Set the work done flag back to false */
  _workDone = false;
  
  // Finally, set the state machine back to STATE_IDLE
  _lastIdleTime = millis();
  state_set(STATE_IDLE);

  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_LISTEN device state. 
 * @return  an integer status
 */
int proc_hdlListen() {
  /* Clear the buffer for receiving status data */
  memset(&_tDecodedPacket, 0, sizeof(_tDecodedPacket));
  memset(&_tDataPayload, 0, sizeof(_tDataPayload));
  memset(&_tStatusPayload, 0, sizeof(_tStatusPayload));
  
  // Listen to data broadcasts from sensor node senders for some time
  DBG_PRINTLN("==> [LIS] Listening for broadcasts.");
  
  _isDataAvailable = false;
  while(millis() - _lastListenTime <= LISTEN_TIMEOUT){
    if(radio_recv() == STATUS_OK) {

      /* Check the type of data received */
      comm_parseHeader(&_tDecodedPacket, _recvBuf, 17);
      
      if(_tDecodedPacket.uContentType == TYPE_REQ_STATUS) {
        DBG_PRINTLN("==> [RX] Received status packet.");
        comm_parseStatusPayload(&_tStatusPayload, 
                                _tDecodedPacket.aPayload,
                                _tDecodedPacket.uContentLen);
        dbg_displayPacketHeader( &_tDecodedPacket );
        dbg_displayStatusPayload( &_tStatusPayload );
      } 
      else if(_tDecodedPacket.uContentType == TYPE_REQ_DATA) {
        DBG_PRINTLN("==> [RX] Received data packet.");
        comm_parseHeader(&_tDecodedPacket, _recvBuf, 17);
        comm_parseDataPayload(&_tDataPayload, 
                              _tDecodedPacket.aPayload,
                              _tDecodedPacket.uContentLen);
        dbg_displayPacketHeader( &_tDecodedPacket );
        dbg_displayDataPayload( &_tDataPayload );
      } 
      else {
        DBG_PRINTLN("==> [RX] Unrecognizable data content type.");
      }

      _isDataAvailable = true;
      
      break; // Break out of while loop once data is received
    }
    delay(500); // Sanity delay
  }
  
  /* Set the state machine to STATE_TRANSMIT */
  _lastTransmitTime = millis();
  state_set(STATE_TRANSMIT);
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_ device state.
 * @return  an integer status
 */
int proc_hdlTransmit() {
  // Transmit only when there is data to transmit
  if(_isDataAvailable == true){
    // Clear the buffer for receiving status data
    memset(&_tDecodedPacket, 0, sizeof(_tDecodedPacket));
    memset(&_sendBuf, '\0', sizeof(_sendBuf)/sizeof(_sendBuf[0]));
  
    // Parse and encode timestamp to the received packet 
    comm_parseHeader(&_tDecodedPacket, _recvBuf, 17);
    _tDecodedPacket.uTimestamp = _now.unixtime();
    comm_writePacket(_sendBuf, &_tDecodedPacket);
  
    while(millis() - _lastTransmitTime <= TRANSMIT_TIMEOUT){
      if(lora_send((char*)_sendBuf, sizeof(_sendBuf)) == STATUS_OK){
        DBG_PRINT("==> [TX] Sent sensor data to aggregator node "); 
        DBG_PRINTLN(DEST_ADDRESS);
        break;
      }
      else{
        DBG_PRINTLN("==> [TX] Retrying sending.");
      }
    }
  }
  /* Start listening again until listening duration is exhausted */
  if (millis() - _lisTxStartTime <= LIS_TX_DURATION) {
    _lastListenTime = millis();
    state_set(STATE_LISTEN);
    return STATUS_OK;
  }

  /* Finally, set the state machine back to STATE_IDLE */
  _lastIdleTime = millis();
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

  DBG_PRINT("Received: ");
  DBG_PRINTLN(aBuf);

  if ( strncmp(aBuf, "END", 3) == 0) {
    return STATUS_OK;
  } else if ( strncmp(aBuf, "SET NODE ADDR ", 14) == 0 ) {
    DBG_PRINT("Node address set to ");
    DBG_PRINTLN((int)(aBuf[14]));
    
  } else if ( strncmp(aBuf, "SET RELAY ADDR ", 15) == 0 ) {
    DBG_PRINT("Relay address set to ");
    DBG_PRINTLN((int)(aBuf[15]));
    
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
    DBG_PRINT("State: ");
    DBG_PRINTLN(_stateStr[(int)(newState)]);
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
/**
* @desc    Initializes both built-in and DS3231 RTCs
* @return  void
*/
void rtc_init() {
    /* Start the built-in RTC */
  _rtc.begin();
  _radioRtc.begin(); // Start the RTC in 24hr mode

  if (_rtc.lostPower()) {
    DBG_PRINTLN("RTC lost power, lets set the time!");
    // following line sets the RTC to the date & time this sketch was compiled
    _rtc.adjust(DateTime(F(__DATE__), F(__TIME__)));
  }
}

/******************************/
/**   Radio Functions        **/
/******************************/
/**
* @desc    Initializes radio
* @return  an integer status
*/
int radio_init() {
  DBG_PRINTLN("Feather Radio Initialization...");
  
  /* Reset the RFM69 radio (?) */
  digitalWrite(RFM69_RST, HIGH);
  delay(10);
  digitalWrite(RFM69_RST, LOW);
  delay(10);

  /* Initialize RF69 Manager */
  if (!_rf69_manager.init()) {
    DBG_PRINTLN("RFM69 radio init failed");
    while (1);
  }
  _rf69_manager.setTimeout(2000);
  
  DBG_PRINTLN("RFM69 radio init OK!");
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM (for low power module)
  // No encryptiond
  if (!_rf69.setFrequency(RF69_FREQ)) {
    DBG_PRINTLN("setFrequency failed");
  }

  // If you are using a high power RF69 eg RFM69HW, you *must* set a Tx power with the
  // ishighpowermodule flag set like this:
  _rf69.setTxPower(20, true);  // range from 14-20 for power, 2nd arg must be true for 69HCW

  // The encryption key has to be the same as the one in the server
  uint8_t key[] = { 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
                    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08};
  _rf69.setEncryptionKey(key);
  DBG_PRINT("RFM69 radio @");  DBG_PRINT((int)RF69_FREQ);  DBG_PRINTLN(" MHz");
  return STATUS_OK;
}

/**
 * @desc    Radio receive
 * @return  an integer status
 */
int radio_recv(){
  if (_rf69_manager.available()) {
    // Wait for a message addressed to us from the client
    uint8_t len = sizeof(_recvBuf);
    uint8_t from;

    if (_rf69_manager.recvfromAck(_recvBuf, &len, &from)) {
      _recvBuf[len] = 0;
      
      DBG_PRINT("Got packet from #"); DBG_PRINT(from);
      DBG_PRINT(" [RSSI :");
      DBG_PRINT(_rf69.lastRssi());
      DBG_PRINTLN("]");

      return STATUS_OK;
    }
  }
  return STATUS_FAILED;
}

/***********************/
/**   LoRa Functions  **/
/***********************/
/**
* @desc    Initialize LoRa
* @return  an integer status
*/
int lora_init(){
  DBG_PRINTLN("Arduino LoRa Initialization...");
  
  // manual reset
  digitalWrite(RFM95_RST, LOW);
  delay(10);
  digitalWrite(RFM95_RST, HIGH);
  delay(10);
 
  while (!_rf95.init()) {
    DBG_PRINTLN("LoRa radio init failed");
    while (1);
  }
  DBG_PRINTLN("LoRa radio init OK!");
 
  // Defaults after init are 434.0MHz, modulation GFSK_Rb250Fd250, +13dbM
  if (!_rf95.setFrequency(RF95_FREQ)) {
    DBG_PRINTLN("setFrequency failed");
    while (1);
  }
  DBG_PRINT("RM95 radio @"); DBG_PRINTLN(RF95_FREQ);
  
  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
 
  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
  // you can set transmitter powers from 5 to 23 dBm:
  _rf95.setTxPower(23, false); 

  return STATUS_OK;
}

/**
* @desc    LoRa Send
* @return  an integer status
*/
int lora_send(char* buf, int len){
  _rf95.send((uint8_t *)buf, len);
  delay(10);
  _rf95.waitPacketSent();

  return STATUS_OK;
}



/***********************/
/**   Dummy Functions **/
/***********************/
int utl_measureBatt() {
  int batt = analogRead(PIN_VBAT);
  batt *= 2; // we divided by 2, so multiply back
  batt *= 3.3; // Multiply by 3.3V, our reference voltage
  batt /= 1024; // convert to voltage
  return batt;
}

void utl_hdlInterrupt(){

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
  _tInputPacket.uContentType = TYPE_REQ_STATUS;
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
  _tStatusPayload.uNodeId          = ID_REL_NODE;
  _tStatusPayload.uPower           = _iBatt;
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


#ifdef DEBUG_MODE
int dbg_displayPacketHeader( tPacket_t* pPacket )
{
  DBG_PRINT("{'Part' : 'Header', 'Content' : {");
  DBG_PRINT(" 'Type' : "); DBG_PRINT((uint8_t)pPacket->uContentType); DBG_PRINT(",");
  DBG_PRINT(" 'Len' : "); DBG_PRINT((uint8_t)pPacket->uContentLen); DBG_PRINT(",");
  DBG_PRINT(" 'MajVer' : "); DBG_PRINT((uint8_t)pPacket->uMajVer); DBG_PRINT(",");
  DBG_PRINT(" 'MinVer' : "); DBG_PRINT((uint8_t)pPacket->uMinVer); DBG_PRINT(",");
  DBG_PRINT(" 'Timestamp' : "); DBG_PRINT((unsigned long)pPacket->uTimestamp);
  DBG_PRINTLN(" }}");
  return STATUS_OK;
}
int dbg_displayDataPayload( tDataPayload_t* pPayload )
{
  DBG_PRINT("{'Part' : 'Data', 'Content' : {");
  DBG_PRINT(" 'Source Node Id' : "); DBG_PRINT((uint16_t)pPayload->uNodeId); DBG_PRINT(",");
  DBG_PRINT(" 'Dest Node Id' : "); DBG_PRINT((uint16_t)pPayload->uRelayId); DBG_PRINT(",");
  DBG_PRINT(" 'pH' : "); DBG_PRINT((uint16_t)pPayload->uPH); DBG_PRINT(",");
  DBG_PRINT(" 'Conductivity' : "); DBG_PRINT((uint16_t)pPayload->uConductivity); DBG_PRINT(",");
  DBG_PRINT(" 'Light' : "); DBG_PRINT((uint16_t)pPayload->uLight); DBG_PRINT(",");
  DBG_PRINT(" 'Temp (Air)' : "); DBG_PRINT((uint16_t)pPayload->uTempAir); DBG_PRINT(",");
  DBG_PRINT(" 'Humidity' : "); DBG_PRINT((uint16_t)pPayload->uHumidity); DBG_PRINT(",");
  DBG_PRINT(" 'Temp (Soil)' : "); DBG_PRINT((uint16_t)pPayload->uTempSoil); DBG_PRINT(",");
  DBG_PRINT(" 'Moisture' : "); DBG_PRINT((uint16_t)pPayload->uMoisture); DBG_PRINT(",");
  DBG_PRINT(" 'Reserved' : "); DBG_PRINT((uint16_t)pPayload->uReserved);
  DBG_PRINTLN(" }}");

  return STATUS_OK;
}

int dbg_displayStatusPayload( tStatusPayload_t* pPayload )
{
  DBG_PRINT("{'Part' : 'Status', 'Content' : {");
  DBG_PRINT(" 'Source Node Id' : "); DBG_PRINT((uint16_t)pPayload->uNodeId); DBG_PRINT(",");
  DBG_PRINT(" 'Power' : "); DBG_PRINT((uint16_t)pPayload->uPower); DBG_PRINT(",");
  DBG_PRINT(" 'Deployment State' : "); DBG_PRINT((uint8_t)pPayload->uDeploymentState); DBG_PRINT(",");
  DBG_PRINT(" 'Status Code' : "); DBG_PRINT((uint8_t)pPayload->uStatusCode);
  DBG_PRINTLN(" }}");

  return STATUS_OK;
}

#endif

