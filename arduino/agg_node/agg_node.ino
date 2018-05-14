/**
   Aggregator Node Program
   CITAS Dryad 2017

   Dependencies
    Libraries
      - RTCLib by Adafruit
      - RadioHead
      - RTCZero
    Boards
      - Arduino SAMD
      - Adafruit SAMD
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

// Transmission-related libraries
#include <SPI.h>
#include <RH_RF95.h> // For the LoRa 9x
#include <RHMesh.h>
#include <RHReliableDatagram.h>

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
// Identifier
#define ID_AGG_NODE       92

// 434 Frequency for CITAS
#define RF95_FREQ         434.0

// Define LoRa
#define ADAFRUIT_LORA_9X

// who am i? (server address)
#define MY_ADDRESS     ID_AGG_NODE

// Pin definitions for LoRa
#if defined(ADAFRUIT_LORA_9X) // Adafruit LoRa
#define RFM95_CS      8
#define RFM95_RST     9
#define RFM95_INT     3
#define LED           13
#endif

// Status variables
#define STATUS_FAILED     -1
#define STATUS_OK         1
#define STATUS_CONTINUE   2

// Battery pin definition
#define VBATPIN A7

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
// Struct definitions
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
int proc_hdlListen();

int comm_sendStatusPacket();

void utl_hdlInterrupt();

int lora_init(void);
int lora_recv();

float utl_measureBatt();

RH_RF95 _rf95(RFM95_CS, RFM95_INT);

int _iPacketNum = 0;
float _fBatt = 0.0;

bool _workDone = false;   /* This flag could be for data collection, retransmission, etc. */

uint8_t _recvBuf[RH_RF95_MAX_MESSAGE_LEN];
uint8_t _sendBuf[RH_RF95_MAX_MESSAGE_LEN];

bool _isDataAvailable = false; // This flag will be used as a condition for transmitting

tPacket_t   _tInputPacket;
tPacket_t   _tDecodedPacket;
tStatusPayload_t _tStatusPayload;
tDataPayload_t _tDataPayload;

/**
   @desc    Setup function implementing initialization of rtc, radio, lora, and
            serial
   @return  void
*/
void setup() {
  while (!Serial) {
    delay(1);
  }

  // Start Serial
  Serial.begin(9600);

  // Assign LED pin mode to Output
  pinMode(LED, OUTPUT);

  // Setup LoRa
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  // Call initialization for lora
  lora_init();

  // Display addresses
  DBG_PRINT("Self address @"); DBG_PRINTLN(MY_ADDRESS);

  return;
}

/**
   @desc    Main looping function. This also contains the switch statement which launches
            different functions depending on the current device state.
   @return  void
*/
void loop() {
  int iRet = 0;

  _fBatt = utl_measureBatt();
  iRet = proc_hdlListen();

  // Sanity delay
  delay(10);

  return;
}

/**
   @desc    Handler for the STATE_LISTEN device state.
   @return  an integer status
*/
int proc_hdlListen() {
  /* Clear the buffer for receiving status data */
  memset(&_tDecodedPacket, 0, sizeof(_tDecodedPacket));
  memset(&_tDataPayload, 0, sizeof(_tDataPayload));
  memset(&_tStatusPayload, 0, sizeof(_tStatusPayload));

  _isDataAvailable = false;
  if (lora_recv() == STATUS_OK) {
    /* Parse the header to determine what type of packet it is */
    comm_parseHeader(&_tDecodedPacket, _recvBuf, LEN_HEADER);
    dbg_displayPacketHeader( &_tDecodedPacket );

    /* Parse the payload accordingly */
    if (_tDecodedPacket.uContentType == TYPE_REQ_STATUS) {
      // Status payload
      comm_parseStatusPayload(&_tStatusPayload,
                              _tDecodedPacket.aPayload,
                              _tDecodedPacket.uContentLen);

      dbg_displayStatusPayload( &_tStatusPayload );

      _isDataAvailable = true;

    } else if (_tDecodedPacket.uContentType == TYPE_REQ_DATA) {
      // Data payload
      comm_parseDataPayload(&_tDataPayload,
                            _tDecodedPacket.aPayload,
                            _tDecodedPacket.uContentLen);

      dbg_displayDataPayload( &_tDataPayload );

      _isDataAvailable = true;

    } else {
      DBG_PRINTLN("No data yet...");
      delay(250);

    }

  }
  delay(200); // Sanity delay


  return STATUS_OK;
}

/***********************/
/**   LoRa Functions  **/
/***********************/
/**
  @desc    Initialize LoRa
  @return  an integer status
*/
int lora_init() {
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
  @desc    LoRa Send
  @return  an integer status
*/
int lora_send(char* buf, int len) {
  DBG_PRINTLN("Start sending.."); delay(10);
  _rf95.send((uint8_t *)buf, len);
  delay(10);
  _rf95.waitPacketSent();

  return STATUS_OK;
}

/**
  @desc    LoRa Receive
  @return  an integer status
*/
int lora_recv() {
  if (_rf95.available()) {
    // Clear buffer
    memset(_recvBuf, '\0', sizeof(_recvBuf) / sizeof(_recvBuf[0]));
    uint8_t len = sizeof(_recvBuf);
    if (_rf95.recv(_recvBuf, &len)) {
      DBG_PRINT("RSSI: ");
      DBG_PRINTLN(_rf95.lastRssi());
      return STATUS_OK;
    }
    else
    {
      DBG_PRINTLN("Receive failed");

    }
  }
  return STATUS_FAILED;
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

void utl_hdlInterrupt() {

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
















