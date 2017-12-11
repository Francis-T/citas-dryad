#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <time.h>

#include <SPI.h>
#include <RH_RF69.h> // For the feather radio
#include <RH_RF95.h> // For the LoRa 9x
#include <RHReliableDatagram.h>
/************ Radio Setup ***************/

// Change to 434.0 or other frequency, must match RX's freq!
#define RF69_FREQ 434.0
#define RF95_FREQ 434.0

// Define Feather and LoRa
#define ARDUINO_SAMD_FEATHER_M0
#define ADAFRUIT_LORA_9X

// change addresses for each client board, any number :)
#define MY_ADDRESS     88

// Where to send packets to!
#define DEST_ADDRESS   90

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

// Payload variables
#define OFFS_HEADER   0
#define OFFS_PAYLOAD  11
#define OFFS_FOOTER   24

#define LEN_HEADER          11
#define LEN_PAYLOAD_DATA    14
#define LEN_PAYLOAD_STATUS  5

#define PROTO_MAJ_VER       0
#define PROTO_MIN_VER       1

#define TYPE_REQ_UNKNOWN    0
#define TYPE_REQ_STATUS     1
#define TYPE_REQ_DATA       2


RH_RF69 _rf69(RFM69_CS, RFM69_INT);              
RH_RF95 _rf95(RFM95_CS, RFM95_INT);
RHReliableDatagram  _rf69_manager(_rf69, MY_ADDRESS);  //Class to manage message delivery and 
                           

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


int rtc_init();

int radio_init(void);
int radio_send(char* buf);

int lora_init(void);
int lora_recv();

uint8_t _buf[RH_RF69_MAX_MESSAGE_LEN];

void setup() 
{
  // Start Serial
  Serial.begin(115200);

  // Assign LED pin mode to Output
  pinMode(LED, OUTPUT);

  // Setup Radio
  pinMode(RFM69_RST, OUTPUT);  
  digitalWrite(RFM69_RST, LOW);

  // Setup LoRa 
  pinMode(RFM95_RST, OUTPUT);
  digitalWrite(RFM95_RST, HIGH);

  // Call initialization for radio and lora
  radio_init();
  lora_init();
   
}

void loop() {

  uint8_t _buf[64];
  uint8_t aRecvBuf[64];
  tPacket_t   tInputPacket;
  tPacket_t   tDecodedPacket;
  tStatusPayload_t tStatusPayload;
  tDataPayload_t tDataPayload;

  /**************************************************/
  /** Test creating and sending of a STATUS packet **/
  /**************************************************/

  /*  Clear all buffers  */
  memset(_buf, '\0', sizeof(_buf)/sizeof(_buf[0]));
  memset(&tInputPacket, 0, sizeof(tInputPacket));
  memset(&tStatusPayload, 0, sizeof(tStatusPayload));

  /* Create the packet header */
  tInputPacket.uContentType = TYPE_REQ_UNKNOWN;
  tInputPacket.uContentLen  = LEN_PAYLOAD_STATUS;
  tInputPacket.uMajVer      = PROTO_MAJ_VER;
  tInputPacket.uMinVer      = PROTO_MIN_VER;
  tInputPacket.uTimestamp   = millis();

  /* Create the status payload */
  tStatusPayload.uNodeId          = 144;
  tStatusPayload.uPower           = 0x03FF;
  tStatusPayload.uDeploymentState = 1;
  tStatusPayload.uStatusCode      = 0xFF;

  /* Write status payload to the packet */
  comm_createStatusPayload(tInputPacket.aPayload, &tStatusPayload);

  /* Finally, write the packet to the sending buffer */
  comm_writePacket(_buf, &tInputPacket);

//  /* Send the packet */
//  Serial.println("Sending status packet...");
//  if(radio_send((char*)_buf) == STATUS_OK){
//    Serial.println("Sending success.");
//  }
//  delay(100);  // Wait 1 second between transmits, could also 'sleep' here!
//

  /************************************************/
  /** Test creating and sending of a DATA packet **/
  /************************************************/

  memset(_buf, '\0', sizeof(_buf)/sizeof(_buf[0]));
  memset(&tDataPayload, 0, sizeof(tDataPayload));

  /* Create the packet header */
  tInputPacket.uContentType = TYPE_REQ_STATUS;
  tInputPacket.uContentLen = LEN_PAYLOAD_DATA;
  tInputPacket.uTimestamp   = millis();

  /* Create the data payload */
  tDataPayload.uNodeId = 144;
  tDataPayload.uRelayId = 145;
  tDataPayload.uPH            = 0x03FF;
  tDataPayload.uConductivity  = 0x03FF;
  tDataPayload.uLight         = 0x03FF;
  tDataPayload.uTempAir       = 0x03FF;
  tDataPayload.uTempSoil      = 0x03FF;
  tDataPayload.uHumidity      = 0x03FF;
  tDataPayload.uMoisture      = 0x03FF;
  tDataPayload.uReserved      = 0x03FF;

  /* Write data payload to the packet */
  comm_createDataPayload(tInputPacket.aPayload, &tDataPayload);

  /* Finally, write the packet to the sending buffer */
  comm_writePacket(_buf, &tInputPacket);

//  /* Send the packet */
//  Serial.println("Sending Data Packet...");
//  if(radio_send((char*)_buf) == STATUS_OK){
//    Serial.println("Sending success.");
//  }
//
//  delay(100);  // Wait 1 second between transmits, could also 'sleep' here!

  char radiopacket[20] = "Hello World #      ";
  if(radio_send((char*)_buf) == STATUS_OK){
    Serial.println("Sending success.");
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

int radio_send(char* radiopacket){
  // Send a message to the DESTINATION!
  if (_rf69_manager.sendtoWait((uint8_t *)radiopacket, strlen(radiopacket), DEST_ADDRESS)) {
    // Now wait for a reply from the server
    uint8_t len = sizeof(_buf);
    uint8_t from;   
    if (_rf69_manager.recvfromAckTimeout(_buf, &len, 2000, &from)) {
      _buf[len] = 0; // zero out remaining string
      
      Serial.print("Got reply from #"); Serial.print(from);
      Serial.print(" [RSSI :");
      Serial.print(_rf69.lastRssi());
      Serial.print("] : ");
      Serial.println((char*)_buf);
    } else {
      Serial.println("No reply, is anyone listening?");
    }
  } else {
    Serial.println("Sending failed (no ack)");
  }
  return STATUS_OK;
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
  Serial.print("Set Freq to: "); Serial.println(RF95_FREQ);
  
  // Defaults after init are 434.0MHz, 13dBm, Bw = 125 kHz, Cr = 4/5, Sf = 128chips/symbol, CRC on
 
  // The default transmitter power is 13dBm, using PA_BOOST.
  // If you are using RFM95/96/97/98 modules which uses the PA_BOOST transmitter pin, then 
  // you can set transmitter powers from 5 to 23 dBm:
  _rf95.setTxPower(23, false); 

  return STATUS_OK;
}

int lora_recv(){
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
