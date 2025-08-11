#!/usr/bin/env python3

import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real, Null
from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.constructeddata import Any

# 디버깅 비활성화
_debug = 0

def extract_value(bacnet_value):
    """BACnet Any 객체에서 실제 값 추출"""
    if bacnet_value is None:
        return None
    
    try:
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean
        
        # 실수형 시도 (analogOutput은 주로 실수)
        try:
            real_val = bacnet_value.cast_out(Real)
            if real_val is not None:
                return float(real_val)
        except:
            pass
        
        # 정수형 시도
        try:
            uint_val = bacnet_value.cast_out(Unsigned)
            if uint_val is not None:
                return int(uint_val)
        except:
            pass
        
        # 문자열 시도
        try:
            str_val = bacnet_value.cast_out(CharacterString)
            if str_val is not None:
                return str(str_val)
        except:
            pass
        
        # 직접 문자열 변환 시도
        return str(bacnet_value)
        
    except:
        return f"값 추출 실패: {bacnet_value}"

async def read_property(app, device_address, object_id, property_id, property_index=None):
    """BACnet 속성 읽기 함수"""
    try:
        request = ReadPropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier=property_id
        )
        
        # 배열 인덱스가 지정된 경우
        if property_index is not None:
            request.propertyArrayIndex = property_index
            
        request.pduDestination = Address(device_address)
        
        response = await app.request(request)
        if response:
            return response.propertyValue
        else:
            return None
    except Exception as e:
        print(f"읽기 오류 ({object_id}.{property_id}): {e}")
        return None

async def write_property(app, device_address, object_id, property_id, value, priority=None):
    """BACnet 속성 쓰기 함수"""
    try:
        from bacpypes3.primitivedata import Real
        
        # 실수 값을 BACnet 형식으로 변환
        bacnet_value = Any(Real(value))
        
        # 쓰기 요청 생성
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier=property_id,
            propertyValue=bacnet_value
        )
        
        # 우선순위 설정
        if priority is not None:
            request.priority = priority
            
        request.pduDestination = Address(device_address)
        
        # 요청 전송
        response = await app.request(request)
        return response is not None
        
    except Exception as e:
        print(f"쓰기 오류 ({object_id}.{property_id}): {e}")
        import traceback
        traceback.print_exc()
        return False

async def read_priority_array(app, device_address, object_id):
    """presentValue의 우선순위 배열 읽기"""
    try:
        print("\n우선순위 배열:")
        active_priorities = []
        
        for i in range(1, 17):  # 우선순위는 1-16
            priority_value_raw = await read_property(app, device_address, object_id, "priorityArray", i)
            priority_value = extract_value(priority_value_raw)
            
            if priority_value and "NULL" not in str(priority_value).upper():
                active_priorities.append((i, priority_value))
                print(f"  우선순위 {i}: {priority_value} [활성]")
            else:
                print(f"  우선순위 {i}: NULL")
        
        # 활성화된 우선순위 요약
        if active_priorities:
            print("\n활성화된 우선순위:")
            for priority, value in active_priorities:
                print(f"  우선순위 {priority}: {value}")
            
            # 가장 높은 우선순위 (가장 낮은 숫자)
            highest_priority = min(active_priorities, key=lambda x: x[0])
            print(f"\n현재 제어 중인 우선순위: {highest_priority[0]} (값: {highest_priority[1]})")
        else:
            print("\n활성화된 우선순위가 없습니다. (모두 NULL)")
            
        return active_priorities
    except Exception as e:
        print(f"우선순위 배열 읽기 오류: {e}")
        import traceback
        traceback.print_exc()
        return None

async def simple_relinquish_test(target_device, object_id, priority=1):
    """매우 단순한 해제 테스트"""
    try:
        # 기본 디바이스 설정
        device = DeviceObject(
            objectName="BACnet Relinquish Test",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        # 애플리케이션 생성
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        print(f"타겟 디바이스: {target_device}")
        print(f"객체: {object_id}")
        print(f"우선순위: {priority}")
        
        # 1. 현재 값 및 우선순위 상태 확인
        print("\n--- 1. 현재 상태 확인 ---")
        
        # 현재 값 읽기
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"현재 값: {current_value}")
        
        # 우선순위 배열 읽기
        await read_priority_array(app, target_device, object_id)
        
        # 2. 테스트 값 설정
        print("\n--- 2. 테스트 값 설정 ---")
        test_value = 99.99
        print(f"설정할 값: {test_value} (우선순위: {priority})")
        await write_property(app, target_device, object_id, "presentValue", test_value, priority)
        
        # 설정 후 확인
        await asyncio.sleep(0.5)
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"설정 후 값: {current_value}")
        
        # 우선순위 배열 확인
        await read_priority_array(app, target_device, object_id)
        
        # 3. relinquishDefault 값 읽기
        print("\n--- 3. relinquishDefault 값 확인 ---")
        relinquish_default_raw = await read_property(app, target_device, object_id, "relinquishDefault")
        relinquish_default = extract_value(relinquish_default_raw)
        print(f"relinquishDefault 값: {relinquish_default}")
        
        # 4. outOfService 상태 확인
        print("\n--- 4. outOfService 상태 확인 ---")
        out_of_service_raw = await read_property(app, target_device, object_id, "outOfService")
        out_of_service = extract_value(out_of_service_raw)
        print(f"outOfService 상태: {out_of_service}")
        
        # 5. 다른 우선순위로 값 설정 (우선순위 2)
        print("\n--- 5. 다른 우선순위로 설정 ---")
        other_priority = 2
        other_value = 77.77
        print(f"다른 우선순위 설정: {other_value} (우선순위: {other_priority})")
        await write_property(app, target_device, object_id, "presentValue", other_value, other_priority)
        
        # 설정 후 확인
        await asyncio.sleep(0.5)
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"설정 후 값: {current_value}")
        
        # 우선순위 배열 확인
        await read_priority_array(app, target_device, object_id)
        
        # 6. relinquishDefault 값으로 설정
        print("\n--- 6. relinquishDefault 값으로 설정 ---")
        
        if relinquish_default is not None:
            print(f"relinquishDefault 값 {relinquish_default}(을)를 우선순위 {priority}에 설정")
            await write_property(app, target_device, object_id, "presentValue", relinquish_default, priority)
            
            # 설정 후 확인
            await asyncio.sleep(0.5)
            current_value_raw = await read_property(app, target_device, object_id, "presentValue")
            current_value = extract_value(current_value_raw)
            print(f"설정 후 값: {current_value}")
            
            # 우선순위 배열 확인
            await read_priority_array(app, target_device, object_id)
        
        # 7. 우선순위 1 및 2 모두 최소값으로 설정
        print("\n--- 7. 최소값으로 설정 ---")
        min_value = 0.0
        
        print(f"우선순위 {priority}에 최소값 {min_value} 설정")
        await write_property(app, target_device, object_id, "presentValue", min_value, priority)
        
        print(f"우선순위 {other_priority}에 최소값 {min_value} 설정")
        await write_property(app, target_device, object_id, "presentValue", min_value, other_priority)
        
        # 설정 후 확인
        await asyncio.sleep(0.5)
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"설정 후 값: {current_value}")
        
        # 우선순위 배열 확인
        await read_priority_array(app, target_device, object_id)
        
        # 8. 대체 방법 제안
        print("\n--- 8. 대체 방법 제안 ---")
        print("BACnet에서 우선순위 배열을 NULL로 설정하는 것은 제한된 방법으로만 가능할 수 있습니다.")
        print("다음 대안을 고려해 보세요:")
        print("1. BACnet 장치 웹 인터페이스 또는 제조업체 소프트웨어 사용")
        print("2. 외부 BACnet 클라이언트 도구 사용 (예: Yabe, BACnet Browser)")
        print("3. 장치 재부팅 또는 리셋 (제한된 경우)")
        print("4. 장치 매뉴얼 확인하여 우선순위 해제 방법 찾기")
        
        print("\n실시간 참고: 장치에 relinquish command 지원 여부 확인하기")
        
        return True
        
    except Exception as e:
        print(f"전체 프로세스 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 함수"""
    # 설정값
    target_device = "200.0.0.162"
    object_id = ("analogOutput", 1)
    priority = 1  # 대상 우선순위
    
    # 우선순위 1 해제 테스트
    await simple_relinquish_test(target_device, object_id, priority)

if __name__ == "__main__":
    print("BACnet 우선순위 해제 테스트")
    print("========================")
    asyncio.run(main())