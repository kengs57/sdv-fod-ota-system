import oracledb
import win32com.client
import time
import math

# 1. DB 접속 정보
db_config = {"user": "ID", "password": "pw", "dsn": "ID.tplinkdns.com:1521/xe"}

# 전역 변수 설정
current_page = 1
all_data = []  
current_panel_features = [None] * 5 

# --- DB 조회 및 패널 업데이트

def get_db_data(vin):
    try:
        conn = oracledb.connect(**db_config)
        cursor = conn.cursor()
        sql_query = """
        SELECT FEATURES_NAME, PRICE, FEATURES_NUM FROM car_features
        WHERE SUPPORTED_CAR_MODEL = (SELECT CAR_MODEL FROM vehicles_owned WHERE VIN = :vin)
          AND FEATURES_NUM NOT IN (
              SELECT FEATURES_NUM FROM order_history WHERE VIN = :vin AND ORDER_STATUS = 'C'
          )
        ORDER BY FEATURES_NUM ASC
        """
        cursor.execute(sql_query, {"vin": vin})
        rows = cursor.fetchall()
        conn.close()
        return rows
    except Exception as e:
        print(f" [DB Error] 조회 실패: {e}")
        return []

def update_panel(fod_vars, rows, page):
    global current_panel_features
    
    total_items = len(rows)
    total_pages = math.ceil(total_items / 5) if total_items > 0 else 1
    page_text = f"{page} / {total_pages}"
    
    try:
        # String 타입 시스템 변수에 텍스트 전송
        fod_vars("CurrentPage").Value = str(page_text)
    except:
        pass

    for i in range(1, 6):
        fod_vars(f"FeatureName_{i}").Value = ""
        current_panel_features[i-1] = None
    
    start_idx = (page - 1) * 5
    page_items = rows[start_idx : start_idx + 5]
    
    for idx, row in enumerate(page_items):
        f_name, price, f_num = row
        fod_vars(f"FeatureName_{idx+1}").Value = f"{f_name} (${price})"
        current_panel_features[idx] = f_num
    
    print(f" [System] 패널 업데이트 완료: {page_text}")

def purchase_by_num(vin, f_num):
    try:
        conn = oracledb.connect(**db_config)
        cursor = conn.cursor()
        sql_insert = """
        INSERT INTO order_history (ORDER_NUM, ORDER_TIME, ORDER_STATUS, VIN, MEMBER_NUM, FEATURES_NUM)
        VALUES (seq_order.NEXTVAL, SYSDATE, 'C', :vin, 1, :f_num)
        """
        cursor.execute(sql_insert, {"vin": vin, "f_num": f_num})
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f" [DB Error] 구매 실패: {e}")
        return False

# --- 메인 실행부 ---
canoe = win32com.client.Dispatch("CANoe.Application")
fod_vars = canoe.System.Namespaces("FoD_UI").Variables
sys_vars = canoe.System.Namespaces("FoD_System").Variables

# 초기 VIN 읽기 및 데이터 로드
current_vin = sys_vars("Current_VIN").Value
last_vin = current_vin 
all_data = get_db_data(current_vin)
update_panel(fod_vars, all_data, current_page)

print(f" [System] 감시 루프 실행 중... (현재 VIN: {current_vin})")

try:
    while True:
        # 0. VIN 변경 감시 (버튼 클릭 등으로 CAPL이 VIN을 바꿨을 때)
        new_vin = sys_vars("Current_VIN").Value
        if new_vin != last_vin:
            print(f" [System] 차량 변경 감지: {last_vin} -> {new_vin}")
            current_vin = new_vin
            last_vin = new_vin
            current_page = 1 # 페이지 초기화
            all_data = get_db_data(current_vin) # 새 차량 데이터 로드
            update_panel(fod_vars, all_data, current_page)

        # 1. 페이지 UP/Down 감시
        if fod_vars("PageUP").Value == 1:
            if len(all_data) > current_page * 5:
                current_page += 1
                update_panel(fod_vars, all_data, current_page)
            fod_vars("PageUP").Value = 0

        if fod_vars("PageDown").Value == 1:
            if current_page > 1:
                current_page -= 1
                update_panel(fod_vars, all_data, current_page)
            fod_vars("PageDown").Value = 0

        # 2. 갱신 요청 (업데이트 버튼)
        if sys_vars("Request_Update").Value == 1:
            all_data = get_db_data(current_vin)
            current_page = 1
            update_panel(fod_vars, all_data, current_page)
            sys_vars("Request_Update").Value = 0

        # 3. 구매 버튼 감시
        for i in range(1, 6):
            if fod_vars(f"BuyBtn_{i}").Value == 1:
                target_f_num = current_panel_features[i-1]
                if target_f_num:
                    if purchase_by_num(current_vin, target_f_num):
                        print(f" [Success] ID {target_f_num} 구매 완료!")
                        fod_vars("PopupVisible").Value = 1 # CAPL 팝업 트리거
                        
                        # 구매 후 목록 최신화
                        all_data = get_db_data(current_vin)
                        if len(all_data) <= (current_page - 1) * 5 and current_page > 1:
                            current_page -= 1
                        update_panel(fod_vars, all_data, current_page)
                fod_vars(f"BuyBtn_{i}").Value = 0
        
        time.sleep(0.1) # 루프 속도 최적화
except KeyboardInterrupt:
    print("종료")