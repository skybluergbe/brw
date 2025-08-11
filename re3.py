#!/usr/bin/env python3

import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real, Unsigned, Boolean, Null
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
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean, Enumerated
        
        # 불린형 시도 (outOfService는 불린)
        try:
            bool_val = bacnet_value.cast_out(Boolean)
            if bool_val is not None:
                return bool(bool_val)
        except:
            pass
        
        # 정수형 시도
        try:
            uint_val = bacnet_value.cast_out(Unsigned)
            if uint_val is not None:
                return int(uint_val)
        except:
            pass
        
        # 실수형 시도
        try:
            real_val = bacnet_value.cast_out(Real)
            if real_val is not None:
                return float(real_val)
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
            return response.propertyValue  # 원본 값 반환
        else:
            return None
    except Exception as e:
        print(f"읽기 오류 ({object_id}.{property_id}): {e}")
        return None

async def read_priority_array(app, device_address, object_id):
    """presentValue의 우선순위 배열 읽기"""
    try:
        # 우선순위 배열 전체를 읽는 것은 무시하고 각 요소를 개별적으로 읽음
        print("\n우선순위 배열:")
        active_priorities = []
        
        for i in range(1, 17):  # 우선순위는 1-16
            priority_raw = await read_property(app, device_address, object_id, "priorityArray", i)
            priority_value = extract_value(priority_raw)
            
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

async def simple_relinquish(target_device, object_id, priority=8):
    """가장 단순한 relinquish 테스트"""
    try:
        # 기본 디바이스 설정
        device = DeviceObject(
            objectName="BACnet Simple Relinquish",
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
        
        # 현재 우선순위 배열 확인
        print("\n현재 우선순위 상태:")
        await read_priority_array(app, target_device, object_id)
        
        # --- 방법 1: PropertyValue 없이 WritePropertyRequest 구성 ---
        print("\n방법 1: 빈 propertyValue로 시도")
        try:
            # 기본 요청 구성
            request = WritePropertyRequest(
                objectIdentifier=ObjectIdentifier(object_id),
                propertyIdentifier="presentValue"
            )
            
            # 우선순위 설정
            request.priority = priority
            request.pduDestination = Address(target_device)
            
            # 요청 전송
            response = await app.request(request)
            
            if response:
                print(f"방법 1 성공: {object_id}.presentValue 우선순위 {priority} 해제됨")
            else:
                print("방법 1 실패")
        except Exception as e:
            print(f"방법 1 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # --- 방법 2: NULL 값으로 직접 쓰기 ---
        print("\n방법 2: Null 값으로 시도")
        try:
            from bacpypes3.basetypes import Null as BACnetNull
            
            # Null 객체 직접 생성
            null_value = BACnetNull()
            
            # 요청 생성
            request = WritePropertyRequest(
                objectIdentifier=ObjectIdentifier(object_id),
                propertyIdentifier="presentValue",
                propertyValue=Any(null_value)
            )
            
            # 우선순위 설정
            request.priority = priority
            request.pduDestination = Address(target_device)
            
            # 요청 전송
            response = await app.request(request)
            
            if response:
                print(f"방법 2 성공: {object_id}.presentValue 우선순위 {priority} 해제됨")
            else:
                print("방법 2 실패")
        except Exception as e:
            print(f"방법 2 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # --- 방법 3: Null 문자열로 시도 ---
        print("\n방법 3: Null 문자열로 시도")
        try:
            from bacpypes3.primitivedata import CharacterString
            
            # "Null" 문자열 값 사용
            request = WritePropertyRequest(
                objectIdentifier=ObjectIdentifier(object_id),
                propertyIdentifier="presentValue",
                propertyValue=Any(CharacterString("Null"))
            )
            
            # 우선순위 설정
            request.priority = priority
            request.pduDestination = Address(target_device)
            
            # 요청 전송
            response = await app.request(request)
            
            if response:
                print(f"방법 3 성공: {object_id}.presentValue 우선순위 {priority} 해제됨")
            else:
                print("방법 3 실패")
        except Exception as e:
            print(f"방법 3 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # --- 최종 상태 확인 ---
        print("\n최종 우선순위 상태:")
        await read_priority_array(app, target_device, object_id)
        
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
    object_id = ("analogOutput", 1)  # 아날로그 출력 객체 또는 ("multiStateValue", 1)
    
    # 우선순위
    priority = 1  # 우선순위 (1-16)
    
    # 간단한 relinquish 테스트 실행
    await simple_relinquish(target_device, object_id, priority)

if __name__ == "__main__":
    print("BACnet 우선순위 해제 테스트")
    print("========================")
    asyncio.run(main())