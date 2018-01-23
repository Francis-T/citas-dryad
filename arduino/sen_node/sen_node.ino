#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <time.h>

#include <RTCZero.h> // Feather internal RTC
#include <SPI.h>
#include <RH_RF69.h> // For the feather radio
#include <RHReliableDatagram.h>

// Sensor node specific libraries
#include <DHT.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <MovingAverage.h>

/*************************/
/*       Definitions     */
/*************************/
// Sensor pins
#define PIN_SOIL_TEMP     6
#define PIN_HUM_AIR_TEMP  9
#define PIN_PH            A0
#define PIN_LIGHT         A3
#define PIN_MOISTURE      A5

// Sensor value offsets
#define OFFSET_PH         1.00 // To be calibrated
#define OFFSET_TEMP       1.00 // To be calibrated

// Change to 434.0 or other frequency, must match RX's freq!
#define RF69_FREQ         434.0

#define DEBUG_MODE

// Define Feather
#define ARDUINO_SAMD_FEATHER_M0

// Battery pin definition
#define PIN_VBAT          A7

// change addresses for each client board, any number :)
#define MY_ADDRESS        88

// Where to send packets to!
#define DEST_ADDRESS      90

// Feather M0 w/Radio
#if defined(ARDUINO_SAMD_FEATHER_M0) 
  #define RFM69_CS        8
  #define RFM69_INT       3
  #define RFM69_RST       4
  #define LED             13
#endif

// Status variables
#define STATUS_FAILED     -1
#define STATUS_OK         1
#define STATUS_CONTINUE   2

// Duration and Timeout in Milliseconds
#define IDLE_TIMEOUT      15000
#define COLLECT_DURATION  10000
#define TRANSMIT_DURATION 10000
#define SLEEP_TIME        10000

/** Note: SLEEP_TIME_SECS is separated here because
 *        the RTC wakeup alarm / timer needs it to
 *        be in seconds instead of millisecs */
#define SLEEP_TIME_SECS   SLEEP_TIME / 1000

// Different possible device states
typedef enum {
  STATE_INACTIVE,
  STATE_UNDEPLOYED,
  STATE_IDLE,
  STATE_ASLEEP,
  STATE_COLLECT,
  STATE_TRANSMIT,
} eState_t;

// Payload variables
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

// Packet struct
typedef struct {
    uint8_t uContentType;
    uint8_t uContentLen;
    uint8_t uMajVer;
    uint8_t uMinVer;
    uint64_t uTimestamp;
    uint8_t aPayload[17];
} tPacket_t;

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

// Equivalent strings for the different eState_ts
char _stateStr[][12] = {
  "INACTIVE",
  "UNDEPLOYED",
  "IDLE",
  "ASLEEP",
  "LISTEN",
  "TRANSMIT",
};

int comm_parseStatusPayload(void*, uint8_t*, uint16_t);
int comm_parseDataPayload(void*, uint8_t*, uint16_t);

typedef int (*fHandlerFunc_t)(void* pPayload, uint8_t* pRecvBuf, uint16_t uRecvLen);

typedef struct {
    uint8_t uContentType;
    fHandlerFunc_t fHandler;
} tDataHandler_t;


tDataHandler_t aDataHdlTbl[] = {
    { TYPE_REQ_STATUS, comm_parseStatusPayload },
    { TYPE_REQ_DATA, comm_parseDataPayload }
};


/*************************/
/* Function Declarations */
/*************************/
void setup();
void loop();

int sensors_init();

int radio_init();
int radio_send(char* buf);

int test_send(boolean stat, boolean data);

void state_set(eState_t newState);
eState_t state_get();
void utl_hdlInterrupt();

int proc_hdlInactive();
int proc_hdlUndeployed();
int proc_hdlIdle();
int proc_hdlAsleep();
int proc_hdlCollect();
int proc_hdlTransmit();

/* Global Variable Declarations */
RTCZero _radioRtc; // Create Feather / radio RTC object
RH_RF69 _rf69(RFM69_CS, RFM69_INT);
RHReliableDatagram  _rf69_manager(_rf69, MY_ADDRESS);

OneWire soilTempWire(PIN_SOIL_TEMP);
DallasTemperature _soilTemp(&soilTempWire);
MovingAverage _ma (0.01);
DHT _humAirTemp (PIN_HUM_AIR_TEMP, DHT22);

eState_t _prevState = STATE_INACTIVE;
eState_t _state = STATE_INACTIVE;

int _iBatt              = 0;
long _lastIdleTime      = 0;
long _lastCollectTime   = 0;
long _lastTransmitTime  = 0;

tPacket_t   _tInputPacket;
tPacket_t   _tDecodedPacket;
tStatusPayload_t _tStatusPayload;
tDataPayload_t _tDataPayload;

bool _workDone = false;   // This flag could be for data collection, retransmission, etc.
bool _isDataAvailable = false; // This flag will be used as a condition for transmitting

uint8_t _sendBuf[RH_RF69_MAX_MESSAGE_LEN];

void setup() 
{
  // Start Serial
  Serial.begin(115200);

  // Assign LED pin mode to Output
  pinMode(LED, OUTPUT);

  // Initialize RTC 
  _radioRtc.begin();

  // Setup sensors
  sensors_init();
  
  // Setup Radio
  pinMode(RFM69_RST, OUTPUT);  
  digitalWrite(RFM69_RST, LOW);

  // Call initialization for radio
  radio_init();
}

void loop() {
  _lastCollectTime = millis();
  _iBatt = analogRead(PIN_VBAT);
  test_send(false, true);
/*
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
      
    case STATE_COLLECT:
      iRet = proc_hdlCollect();
      break;

    case STATE_TRANSMIT:
      iRet = proc_hdlTransmit();
      break;
      
    default:
      break;
  }

  // Sanity delay
  delay(10);

  return;*/
}

int test_send(boolean stat, boolean data){

  if(stat == true){
    /**************************************************/
    /** Test creating and sending of a STATUS packet **/
    /**************************************************/
    /*  Clear all buffers  */
    memset(_sendBuf, '\0', sizeof(_sendBuf)/sizeof(_sendBuf[0]));
    memset(&_tInputPacket, 0, sizeof(_tInputPacket));
    memset(&_tStatusPayload, 0, sizeof(_tStatusPayload));
  
    /* Create the packet header */
    _tInputPacket.uContentType = TYPE_REQ_UNKNOWN;
    _tInputPacket.uContentLen  = LEN_PAYLOAD_STATUS;
    _tInputPacket.uMajVer      = PROTO_MAJ_VER;
    _tInputPacket.uMinVer      = PROTO_MIN_VER;
    _tInputPacket.uTimestamp   = millis();
  
    /* Create the status payload */
    _tStatusPayload.uNodeId          = 144;
    _tStatusPayload.uPower           = _iBatt;
    _tStatusPayload.uDeploymentState = 1;
    _tStatusPayload.uStatusCode      = 0xFF;
  
    /* Write status payload to the packet */
    comm_createStatusPayload(_tInputPacket.aPayload, &_tStatusPayload);
  
    /* Finally, write the packet to the sending buffer */
    comm_writePacket(_sendBuf, &_tInputPacket);


    for (int i = 0; i < RH_RF69_MAX_MESSAGE_LEN; i++) {
      Serial.print(_sendBuf[i]);
      Serial.print(" ");
    }
    Serial.println();
    /* Send the packet */
    Serial.println("Sending status packet...");
    if(radio_send((char*)_sendBuf) == STATUS_OK){
      Serial.println("Sending success.");
    }
  }
  
  if(data==true){
    /************************************************/
    /** Test creating and sending of a DATA packet **/
    /************************************************/
  
    memset(_sendBuf, '\0', sizeof(_sendBuf)/sizeof(_sendBuf[0]));
    memset(&_tDataPayload, 0, sizeof(_tDataPayload));
    memset(&_tInputPacket, 0, sizeof(_tInputPacket));
  
    /* Create the packet header */
    _tInputPacket.uContentType = TYPE_REQ_DATA;
    _tInputPacket.uContentLen  = LEN_PAYLOAD_DATA;
    _tInputPacket.uMajVer      = PROTO_MAJ_VER;
    _tInputPacket.uMinVer      = PROTO_MIN_VER;
    _tInputPacket.uTimestamp   = millis();

    // Updating Moving Average
    _ma.update(analogRead(PIN_MOISTURE));

    /* Create the data payload */
    _tDataPayload.uNodeId        = 144;
    _tDataPayload.uRelayId       = 145;
    _tDataPayload.uPH            = analogRead(PIN_PH);
    _tDataPayload.uConductivity  = 0x03FF;
    _tDataPayload.uLight         = analogRead(PIN_LIGHT);
    _tDataPayload.uTempAir       = _humAirTemp.readTemperature();
    _tDataPayload.uTempSoil      = digitalRead(PIN_SOIL_TEMP);
    _tDataPayload.uHumidity      = _humAirTemp.readHumidity();
    _tDataPayload.uMoisture      = _ma.get();
    _tDataPayload.uReserved      = 0x03FF;
  
    /* Write data payload to the packet */
    comm_createDataPayload(_tInputPacket.aPayload, &_tDataPayload);
    
    /* Finally, write the packet to the sending buffer */
    comm_writePacket(_sendBuf, &_tInputPacket);
    for(int i=0; i < RH_RF69_MAX_MESSAGE_LEN; i++){
      Serial.print(_sendBuf[i]); 
      Serial.print(" ");
    }
    Serial.println();
  
    /* Send the packet */
    Serial.println("Sending Data Packet...");
    if(radio_send((char*)_sendBuf) == STATUS_OK){
      Serial.println("Sending success.");
    }
  }

  delay(100);  // Wait 1 second between transmits, could also 'sleep' here!
  return STATUS_OK;
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
        Serial.println("Starting processes...");
        delay(10);
//  }
  _lastIdleTime = millis();
  state_set(STATE_IDLE);
  
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_IDLE. A state that simply waits for events to be done.
 * 
 *          If the device enters this state while the 'work' is not yet done (as indicated 
 *          by the _workDone flag), then it immediately transitions to STATE_COLLECT instead.
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
    /* Record time before COLLECT */
    _lastCollectTime = millis();
    state_set(STATE_COLLECT);
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
  Serial.println("After detach");
  delay(10000);

  /* Set the work done flag back to false */
  _workDone = false;
  
  // Finally, set the state machine back to STATE_IDLE
  _lastIdleTime = millis();
  state_set(STATE_IDLE);

  Serial.println("Send status packet called!");
  // Send status packet before Idling
  if(comm_sendStatusPacket() == STATUS_OK){
    Serial.println("Status Packet Sent!");
  }
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_COLLECT device state. 
 * @return  an integer status
 */
int proc_hdlCollect() {
  _isDataAvailable = false;

  /* Clear the buffers */
  memset(_sendBuf, '\0', sizeof(_sendBuf)/sizeof(_sendBuf[0]));
  memset(&_tDataPayload, 0, sizeof(_tDataPayload));
  memset(&_tInputPacket, 0, sizeof(_tInputPacket));

  Serial.println("Start reading...");

  // Updating Moving Average
  _ma.update(analogRead(PIN_MOISTURE));

  /* Create the data payload */
  _tDataPayload.uNodeId        = 144;
  _tDataPayload.uRelayId       = 145;
  _tDataPayload.uPH            = analogRead(PIN_PH);
  _tDataPayload.uConductivity  = 0x03FF;
  _tDataPayload.uLight         = analogRead(PIN_LIGHT);
  _tDataPayload.uTempAir       = _humAirTemp.readTemperature();
  _tDataPayload.uTempSoil      = digitalRead(PIN_SOIL_TEMP);
  _tDataPayload.uHumidity      = _humAirTemp.readHumidity();
  _tDataPayload.uMoisture      = _ma.get();
  _tDataPayload.uReserved      = 0x03FF;

  /* Write data payload to the packet */
  comm_createDataPayload(_tInputPacket.aPayload, &_tDataPayload);

  /* Finally, write the packet to the sending buffer */
  comm_writePacket(_sendBuf, &_tInputPacket);

  _isDataAvailable = true;
  delay(200);
  
  /* Record time before Transmitting*/
  _lastTransmitTime = millis();
  
  /* Set the state machine to STATE_TRANSMIT */
  state_set(STATE_TRANSMIT);
  return STATUS_OK;
}

/**
 * @desc    Handler for the STATE_ device state.
 * @return  an integer status
 */
int proc_hdlTransmit() {
  /* Transmit cached data to destination node */
  if(_isDataAvailable == true){
  
    while(millis() - _lastTransmitTime <= TRANSMIT_DURATION){
      if(radio_send((char*)_sendBuf) == STATUS_OK){
        // TODO add number of sending trials?
        break;
      }
    }
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

  Serial.print("Received: ");
  Serial.println(aBuf);

  if ( strncmp(aBuf, "END", 3) == 0) {
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
    Serial.print("State: ");    Serial.println(_stateStr[(int)(newState)]);
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

/***********************/
/**   Dummy Functions **/
/***********************/
/*
float utl_measureBatt() {
  float batt = analogRead(PIN_VBAT);
  batt *= 2; // we divided by 2, so multiply back
  batt *= 3.3; // Multiply by 3.3V, our reference voltage
  batt /= 1024; // convert to voltage
  return batt;
}*/

void utl_hdlInterrupt(){

}

/******************************/
/**   Sensor Functions       **/
/******************************/
int sensors_init(){
  // Begin commands for sensors
  _humAirTemp.begin();
  _soilTemp.begin();
  // Moving average for smoothing moisture values
  _ma.reset(analogRead(PIN_MOISTURE));
  return STATUS_OK;
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

int radio_send(char* radiopacket){
  // Send a message to the DESTINATION!
  
  if (_rf69_manager.sendtoWait((uint8_t *)radiopacket, strlen(radiopacket), DEST_ADDRESS)) {
    // Now wait for a reply from the server
    uint8_t len = sizeof(_sendBuf);
    uint8_t from;   
    if (_rf69_manager.recvfromAckTimeout(_sendBuf, &len, 2000, &from)) {
      _sendBuf[len] = 0; // zero out remaining string
      
      Serial.print("Got reply from #"); Serial.print(from);
      Serial.print(" [RSSI :");
      Serial.print(_rf69.lastRssi());
      Serial.print("] : ");
      Serial.println((char*)_sendBuf);
    } else {
      Serial.println("No reply, is anyone listening?");
    }
  } else {
    Serial.println("Sending failed (no ack)");
  }
  return STATUS_OK;
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
  _tStatusPayload.uPower           = _iBatt;
  _tStatusPayload.uDeploymentState = 1;
  _tStatusPayload.uStatusCode      = 0xFF;

  // Creating and writing status payload to input packet
  comm_createStatusPayload(_tInputPacket.aPayload, &_tStatusPayload);
  comm_writePacket(_sendBuf, &_tInputPacket);

  // Send the packet
  if(radio_send((char *)_sendBuf) == STATUS_OK){
    return STATUS_OK;
  }

  return STATUS_FAILED;
}

#ifdef DEBUG_MODE
int dbg_displayPacketHeader( tPacket_t* pPacket )
{
    Serial.println("Header:");
    Serial.print("    Type: "); Serial.println((uint8_t)pPacket->uContentType);
    Serial.print("    Len: "); Serial.println((uint8_t)pPacket->uContentLen);
    Serial.print("    MajVer: "); Serial.println((uint8_t)pPacket->uMajVer); 
    Serial.print("    MinVer: "); Serial.println((uint8_t)pPacket->uMinVer);
    Serial.print("    Timestamp: "); Serial.println((unsigned long)pPacket->uTimestamp);

    return STATUS_OK;
}
#endif
