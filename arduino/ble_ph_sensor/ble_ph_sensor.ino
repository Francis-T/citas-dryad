#include "string.h"
#include "LowPower.h"

#define TRUE  1
#define FALSE 0

#define STATUS_FAILED     0
#define STATUS_OK         1
#define STATUS_DATA_RECVD 2

#define DEF_NOTIF_INTERVAL    20000
#define MAX_NOTIF_ACTIVE_TIME 360000
#define CATCH_QUERY_DURATION  2000

#define MATCHED 0

#define DEPLOY_STATUS_PIN 2
#define PH_SENSOR_PIN     A1
#define BATT_LEVEL_PIN    A2

typedef enum {
  UNKNOWN, INACTIVE, IDLE, BUSY
} eState_t;

char  _aRecvBuf[20] = {};
int   _iRecvIdx = 0;
int   _bLiveNotif = FALSE;
int   _bFirstActivate = TRUE;
long  _lLastNotif = 0;
long  _lNotifStartTime = 0;


long  _lStartTime = 0;
eState_t _eState = UNKNOWN;

int utl_match(const char* s1, const char* s2, int iLen);
int dat_procRequest(char* aMsg, int iLen);
int com_recv(char* aBuf);

void setup() {

  /*
   * +++ //no line ending
   * AT+USBDEBUG=OFF //both nl cr
   * AT+BLUNODEBUG=OFF
   * AT+NAME=[]
   * AT+EXIT
   * +++
   */
  Serial.begin(115200);

  pinMode(DEPLOY_STATUS_PIN, OUTPUT);
  digitalWrite(DEPLOY_STATUS_PIN, LOW);

  pinMode(13, OUTPUT);

  _lStartTime = millis();
  sys_setState(INACTIVE);
  //sys_setState(IDLE);
  return;
}

void loop() {
  if (_bFirstActivate) {
    digitalWrite(DEPLOY_STATUS_PIN, HIGH);
    delay(50);
    digitalWrite(DEPLOY_STATUS_PIN, LOW);
    delay(50);
    digitalWrite(DEPLOY_STATUS_PIN, HIGH);
    delay(50);
    digitalWrite(DEPLOY_STATUS_PIN, LOW);
    _bFirstActivate = FALSE;
  }
  
  _iRecvIdx = 0;
  memset(_aRecvBuf, 0, sizeof(_aRecvBuf));

  int iRetVal = com_recv(_aRecvBuf);
  if (iRetVal == STATUS_FAILED) {
    delay(90);
    return;
  }

  if (iRetVal == STATUS_DATA_RECVD) {
    if (dat_procRequest(_aRecvBuf, _iRecvIdx) <= STATUS_FAILED) {
      // Failed
      return;
    }
  }

  if (_bLiveNotif) {
    if (dat_liveNotif() <= STATUS_FAILED) {
      // FAILED
      return;
    }
  }

  delay(90);
  if((_lStartTime + CATCH_QUERY_DURATION) < millis()){ 
    digitalWrite(DEPLOY_STATUS_PIN, HIGH);
    delay(500);
    digitalWrite(DEPLOY_STATUS_PIN, LOW);
    _bFirstActivate = TRUE;
    LowPower.powerDown(SLEEP_8S, ADC_OFF, BOD_OFF);
    _lStartTime = millis();
  }
  return;
}

int com_recv(char* aBuf) {
  if (Serial.available() > 0) {
    _lStartTime = millis();
    char c = 1;
    while (c >= 0) {
      c = Serial.read();
      if ((c <= ' ') && (_iRecvIdx == 0)) {
        delay(50);
        continue;
      }
      _aRecvBuf[_iRecvIdx++] = c;
      delay(50);
    }
    return STATUS_DATA_RECVD;
  }

  return STATUS_OK;
}

int dat_respSensor() {
  char aBaseStr[64];
  char aValStrPH[10];
  char aValStrBatt[10];
  
  memset(aBaseStr, 0, sizeof(aBaseStr));
  memset(aValStrPH, 0, sizeof(aValStrPH));
  memset(aValStrBatt, 0, sizeof(aValStrBatt));

// float dVal = 14.0 * (random(20, 80) / 100.0);

  // PH data
  int iAdcValPH = analogRead(PH_SENSOR_PIN);
  float dVoltagePH = (iAdcValPH * 5.0) / 1024;
  float dValPH = dVoltagePH;
// float dValPH = dVoltagePH * 2.2570 + 2.6675;

  // Battery data
  int dMaxBatt = 3.7;
  int iAdcValBatt = analogRead(BATT_LEVEL_PIN);
  float dValBatt = (iAdcValBatt * dMaxBatt / 2) / 1024;

  dtostrf(dValPH, 6, 2, aValStrPH);
  dtostrf(dValBatt, 6, 2, aValStrBatt);
  
  strcpy(aBaseStr, " RDATA: pH=");
  strcat(aBaseStr, aValStrPH);
  strcat(aBaseStr, ";");
  Serial.println(aBaseStr);
  
  strcpy(aBaseStr, " RDATA: bt=");
  strcat(aBaseStr, aValStrBatt);
  strcat(aBaseStr, ";");
  Serial.println(aBaseStr);
 
}

int dat_liveNotif() {
  /* If the current time since our last notif is greater than
    DEF_NOTIF_INTERVAL, then send out a reading */
  if ( (_lLastNotif + DEF_NOTIF_INTERVAL) < millis() ) {
    dat_respSensor();
    _lLastNotif = millis();
  }

  /* If we exceed the maximum active time for notifs, then we
      must auto-deactivate for the sake of power */
  if ((_lNotifStartTime + MAX_NOTIF_ACTIVE_TIME) < millis()) {
    dat_stopLiveNotif();
    Serial.println(" RDEND:OK;");
  }

  return STATUS_OK;
}

int dat_procRequest(char* aMsg, int iLen) {
  int iResult = STATUS_FAILED;
  
  if (utl_match(aMsg, "QREAD", 5)) {
    iResult = req_read(aMsg, iLen);
      
  } else if (utl_match(aMsg, "QSTOP", 5)) {
    iResult = req_stop(aMsg, iLen);
    
  } else if (utl_match(aMsg, "QDEPL", 5)) {
    iResult = req_deploy(aMsg, iLen);
    
  } else if (utl_match(aMsg, "QUNDP", 5)) {
    iResult = req_undeploy(aMsg, iLen);
    
  } else if (utl_match(aMsg, "QSTAT", 5)) {
    iResult = req_state(aMsg, iLen);
    
  } else {
    Serial.println(" RUNKN:ERR_INV_CMD;");
  }

  return iResult;
}

int dat_resetLiveNotif() {
  _bLiveNotif = TRUE;
  _lNotifStartTime = millis();
  return STATUS_OK;
}

int dat_stopLiveNotif() {
  _bLiveNotif = FALSE;
  _lNotifStartTime = 0;
  sys_setState(IDLE);
  return STATUS_OK;
}

int req_read(char* pMsg, int iLen) {
  dat_resetLiveNotif();
  sys_setState(BUSY);
  //Serial.println(" RREAD:OK;");
  delay(100);
  dat_respSensor();
  //Serial.println(" RDSTA:OK;");
  sys_setState(IDLE);
  
  return STATUS_OK;
}

int req_stop(char* aMsg, int iLen) {
    if (sys_getState() == BUSY) {
      dat_stopLiveNotif();
      Serial.println(" RDEND:OK;");
      delay(250);
      sys_setState(IDLE);
      Serial.println(" RSTOP:OK;");
    } else {
      Serial.println(" RSTOP:ERR_INV_STATE;");
     return STATUS_FAILED;
    }
  
  return STATUS_OK;
}

int req_deploy(char* pMsg, int iLen) {
  if (sys_getState() == INACTIVE) {
//    digitalWrite(DEPLOY_STATUS_PIN, LOW);
    sys_setState(IDLE);
    Serial.println(" RDEPL:OK;");
  } else {
    Serial.println(" RDEPL:ERR_INV_STATE;");
    return STATUS_FAILED;
  }
  
  return STATUS_OK;  
}

int req_undeploy(char* pMsg, int iLen) {
    if ((sys_getState() == IDLE) || 
        (sys_getState() == BUSY)) {
      /* Stop any ongoing read sessions when we undeploy */
      req_stop(pMsg, iLen);
      
//      digitalWrite(DEPLOY_STATUS_PIN, HIGH);
      sys_setState(INACTIVE);
      Serial.println(" RUNDP:OK;");
    } else {
      Serial.println(" RUNDP:ERR_INV_STATE;");
      return STATUS_FAILED;
    }

    return STATUS_OK;
}

int req_state(char* pMsg, int iLen) {
    switch(_eState) {
      case INACTIVE:
        Serial.println(" RSTAT:INACTIVE;");
        break;
      case IDLE:
        Serial.println(" RSTAT:IDLE;");
        break;
      case BUSY:
        Serial.println(" RSTAT:BUSY;");
        break;
      default:
        Serial.println(" RSTAT:UNKNOWN;");
        break;
    }
    
    return STATUS_OK;
}

void sys_setState(eState_t eNewState) {
  _eState = eNewState;
  return;
}

eState_t sys_getState() {
  return _eState;
}

int utl_match(const char* s1, const char* s2, int iLen) {
  return strncmp(s1, s2, iLen) == 0 ? TRUE : FALSE;
}

