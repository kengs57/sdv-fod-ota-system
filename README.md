
```markdown
# Cloud 기반 FoD(구독형) 서비스 - vECU 기능 추가를 위한 OTA 프로세스 구현

> **현대모비스 x 멋쟁이사자처럼 모비우스 부트캠프 1기 PBL 3-2팀 (Soda CAN)**  
> **개발 기간:** 2026.02 - 2026.03 (7주간 자동차 V-Model 라이프사이클 기반 수행)  
> **담당 역할:** 팀장 / 기능구매부(PC1) 시스템 구축, Python 미들웨어 및 Oracle DB 인프라 설계

---

## 1. 프로젝트 개요

SDV(소프트웨어 정의 차량) 패러다임 전환에 맞춰 출고 이후에도 소프트웨어 업데이트를 통해 차량의 가치를 지속적으로 진화시키는 엔드투엔드(End-to-End) 시스템을 구축했습니다. 

AWS 클라우드 인프라와 Vector CANoe 가상 차량 환경을 실시간으로 연동하여 **차대번호(VIN) 기반 맞춤형 FoD(Feature on Demand) 구매** 및 **OTA(Over-the-Air) 고장 진단 및 복구 프로세스**를 구현하고 V-Model 프로세스로 검증했습니다.

---

## 2. 주요 시연 (PC1 기능구매부 시연)

* **차대번호(VIN) 인식 및 카탈로그 분기:** 패널에서 GV80(`KMHJM511KP123456`) 또는 CASPER(`KMHRA511SR123456`) 선택 시 차량별 지원 기능을 클라우드 DB에서 실시간 조회
* **동적 필터링 & 페이징:** `car_features`(판매 기능)와 `order_history`(사용자 구매 이력)를 연계 검증하여 미보유 기능만 구매 패널(BUY 1~5)에 표출
* **트랜잭션 피드백:** 앰비언트 라이트 색상 구매 시 클라우드 DB에 트랜잭션 INSERT 후 패널에 2초간 `Order Confirmed` 팝업 표출 및 CAN 버스로 활성화 신호 전송

---

## 3. 시스템 아키텍처 (Car-to-Cloud)

```text
+-----------------------------------------------------------------------------------+
|                        Vector CANoe 가상 차량 환경 (HMI & vECU)                   |
|                                                                                   |
|  [PC1: 기능구매부]              [PC2: 앰비언트 라이트]          [PC3: 내비게이션]  |
|  - 차대번호(VIN) 매핑           - 색상 Unlock 제어             - 강제 결함 주입   |
|  - 기능 조회/구매 패널          - HMI 조명 제어/점등           - OTA 복구 및 갱신 |
+------------------------------------------+----------------------------------------+
                                           | CAN Bus 통신 (CAN ID: 0x100 ~ 0x430)
                                           v
+-----------------------------------------------------------------------------------+
|                            차량 통신 게이트웨이 (TCU / VUM)                       |
+------------------------------------------+----------------------------------------+
                                           | REST API / Socket
                                           v
+-----------------------------------------------------------------------------------+
|                          Python Middleware Bridge Service                         |
|  - CANoe System Variables (SysVar) 실시간 모니터링 및 트리거 감지                |
|  - Oracle SQL 질의 및 결과 데이터 JSON 포맷팅 브릿지                              |
+------------------------------------------+----------------------------------------+
                                           | cx_Oracle Connection Pool
                                           v
+-----------------------------------------------------------------------------------+
|                        AWS Docker 기반 Oracle Cloud Database                      |
|  - 다중 세션 동시성 보장 및 데드락(Deadlock) 방지 트랜잭션 제어                  |
+-----------------------------------------------------------------------------------+

```

### 데이터베이스 모델링 (ERD)

* **Member:** 회원 계정 정보 (`MEMBER_NUM` PK)
* **Vehicles_owned:** 사용자 소유 차량 및 VIN 정보 (`VIN` PK, `MEMBER_NUM` FK)
* **Car_features:** 차량 모델별 지원 FoD 기능 정의 (`FEATURES_NUM` PK)
* **Order_History:** 기능 구매 내역 및 결제 상태 (`ORDER_NUM` PK, `VIN`, `MEMBER_NUM`, `FEATURES_NUM` FK)
* **SW_version:** 차종별 내비게이션 최신 바이너리 버전 (`SW_NAME` PK)

---

## 4. CAN 통신 사양 (Communication Specification)

### PC1 (기능구매부) 통신 매트릭스

| Message Name | CAN ID | DLC | Tx Method | Transmitter | Receiver | Signals & Details |
| --- | --- | --- | --- | --- | --- | --- |
| `msg_order_request` | `0x400` | 2 | Event | OrderPanel ECU | TCU | `selected_feature_id` (0~7 bit), `purchase_trigger` (8 bit) |
| `msg_order_state` | `0x410` | 2 | Event | TCU | OrderPanel ECU | `order_status_result` (1:Success, 2:Pending, 3:Fail), `confirmed_feature_id` |
| `msg_list_refresh` | `0x420` | 1 | Event | OrderPanel ECU | TCU | `purchase_list_refresh_req` (0 bit: 리스트 갱신 요청) |
| `msg_list_ready` | `0x430` | 1 | Event | TCU | OrderPanel ECU | `data_file_ready_flag` (0 bit: 데이터 파일 생성 완료 알림) |

### PC2 (앰비언트 라이트) & PC3 (내비게이션) 통신 매트릭스

* **PC2 (0x110 ~ 0x150):** `msg_panel`(0x110), `msg_ambient_ctrl`(0x120), `msg_tcu_req`(0x130), `msg_tcu_res`(0x140), `msg_light_output`(0x150)
* **PC3 (0x100 ~ 0x300):** `msg_nav`(0x100), `msg_vum`(0x200), `msg_tcu`(0x300)

---

## 5. V-Model 기반 엔지니어링 및 검증 성과

본 프로젝트는 요구사항 도출부터 단위 테스트, 시나리오 테스트까지 전 과정을 검증하였습니다.

```text
[요구사항 분석] REQ_001 ~ REQ_021 ====================> [인수 테스트] 데모 시연 및 E2E 시나리오 (Pass)
      \                                                       /
   [시스템 설계] C2C 아키텍처, DBC 사양 ============> [시스템 테스트] 안전 조건(속도=0), 에러 처리 (Pass)
         \                                             /
      [모듈 설계] DB ERD, CAPL 로직 ============> [단위 테스트] API 엔드포인트, DB 쿼리, CAPL 검증 (Pass)
            \                                     /
             [구현] Oracle DB / Python / CAPL / Panel

```

* **단위 테스트 (Unit Test):**
* `OrderPanel ECU`: 패널 조작 시 `Current_VIN`, `BuyBtn` 변수 즉각 변경 검증 (Pass)
* `Python Middleware`: VIN 변경 감지 및 DB 실시간 동기화 함수(`get_db_data`) 호출 검증 (Pass)
* `TCU (Simulated)`: 구매 요청 시 `ORDER_HISTORY` 시퀀스 및 주문 상태 레코드 생성 검증 (Pass)
* `Cloud Database`: 다중 PC(PC1~PC3) 동시 접속 환경에서의 데드락 방지 및 트랜잭션 무결성 검증 (Pass)


* **시나리오 테스트 (Scenario Test):**
* **시나리오 1 (FoD 구매 및 조명 언락):** Scene 1 ~ Scene 16 전 항목 Pass
* **시나리오 2 (내비게이션 결함 주입 및 OTA 복구):** Scene 1 ~ Scene 7 전 항목 Pass
* **시나리오 3 (클라우드 인프라 안정성):** Scene 1 ~ Scene 5 전 항목 Pass



---

## 6. 리포지토리 구성

```text
├── docs/                               # 프로젝트 산출물 문서
│   ├── PBL_Presentation.pdf            # 최종 발표 자료
│   ├── PBL_Poster.pdf                  # 포스터 세션 자료
│   └── Engineering_Artifacts.xlsx      # V-Model 공학 산출물 (요구사항, DBC, 매트릭스)
├── database/                           # 데이터베이스 스크립트
│   └── TABLE.sql                       # Oracle DB DDL 및 초기 데이터 쿼리
├── middleware/                         # 통신 미들웨어
│   ├── pc1_middleware.py               # CANoe-DB 실시간 양방향 연동 스크립트
│   └── config.py.example               # 접속 정보 템플릿
└── simulation/                         # Vector CANoe 시뮬레이션 환경
    ├── 3_2team_PC1.dbc                 # PC1 CAN 통신 데이터베이스
    ├── 3_2team_PC2.dbc                 # PC2 CAN 통신 데이터베이스
    ├── 3_2team_PC3.dbc                 # PC3 CAN 통신 데이터베이스
    └── SodaCAN_PC1/
        ├── PC1_CAPL_03.can             # PC1 가상 노드 제어 CAPL 코드
        ├── PC1_Panel1.xvp              # Panel Designer UI 정의 파일
        ├── SodaCAN_PC1.cfg             # CANoe 프로젝트 설정 파일
        └── SodaCAN_PC1.stcfg           # 시스템 변수(System Variables) 설정 파일

```

---

## 7. 기술 스택 (Tech Stack)

* **Vehicle Simulation:** Vector CANoe, Panel Designer, CANdb++, CAPL
* **Protocols:** CAN, CAN FD, UDS/DoIP (Concept)
* **Middleware & Backend:** Python 3.x, `python-can`, `cx_Oracle`
* **Database & Cloud:** Oracle Database 21c (XE), Docker, AWS EC2

```

```
