#!/usr/bin/env python3

import asyncio
import sys
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real
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
        # 우선순위 배열 전체를 읽는 것은 무시하고 각 요소를 개별적으로 읽음
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

async def set_relinquish_with_bacnet_stack(target_device, object_id, priority):
    """직접 BACnet 스택 호출"""
    try:
        print("\n시스템 명령으로 해제 시도")
        
        # BACpypes3 버전 확인
        import bacpypes3
        print(f"BACpypes3 버전: {getattr(bacpypes3, '__version__', '알 수 없음')}")
        
        # BACnet 스택 명령어 실행
        print("relinquish_default 명령 실행...")
        
        # 객체 ID 형식 준비
        object_type, object_instance = object_id
        object_type_str = object_type.replace("Output", "-output").replace("Value", "-value")
        
        # 명령어 생성
        # 참고: 실제 환경에서는 작동하지 않을 수 있음
        import subprocess
        
        cmd = [
            sys.executable, "-m", "bacpypes3.app.command",
            "write", f"{target_device}", 
            f"{object_type_str}:{object_instance}", "present-value",
            "--priority", f"{priority}", "--null"
        ]
        
        print(f"실행 명령어: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print(f"반환 코드: {result.returncode}")
        print(f"출력: {result.stdout}")
        
        if result.stderr:
            print(f"오류: {result.stderr}")
        
        return result.returncode == 0
    except Exception as e:
        print(f"스택 호출 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def simple_relinquish_test(target_device, object_id, priority=8):
    """매우 단순한 relinquish 테스트"""
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
        
        # 현재 값 읽기
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"\n현재 값: {current_value}")
        
        # 현재 우선순위 배열 읽기
        await read_priority_array(app, target_device, object_id)
        
        # 1. 먼저 값 설정 (테스트용)
        print("\n1. 테스트 값 설정 (값: 12.34)")
        await write_property(app, target_device, object_id, "presentValue", 12.34, priority)
        
        # 확인
        await asyncio.sleep(0.5)
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"\n값 설정 후: {current_value}")
        
        # 우선순위 배열 확인
        await read_priority_array(app, target_device, object_id)
        
        # 2. 직접 스택 호출로 해제 시도
        success = await set_relinquish_with_bacnet_stack(target_device, object_id, priority)
        
        # 결과 확인
        if success:
            print("\n해제 성공!")
        else:
            print("\n해제 실패. 직접 명령어로 시도해 보세요:")
            print(f"python -m bacpypes3.app.command write {target_device} {object_id[0].replace('Output', '-output')}:{object_id[1]} present-value --priority {priority} --null")
        
        # 3. 다시 값 확인
        await asyncio.sleep(0.5)
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"\n최종 값: {current_value}")
        
        # 최종 우선순위 배열 확인
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
    object_id = ("analogOutput", 1)
    priority = 8
    
    # NULL 값 쓰기 시도
    await simple_relinquish_test(target_device, object_id, priority)
    
    # 별도 명령어 출력
    print("\n\n===== 별도 명령어로 시도 =====")
    print("다음 명령어를 직접 실행해 보세요:")
    print(f"python -m bacpypes3.app.command write {target_device} {object_id[0].replace('Output', '-output')}:{object_id[1]} present-value --priority {priority} --null")

if __name__ == "__main__":
    print("BACnet AnalogOutput NULL 값 쓰기 테스트")
    print("===================================")
    asyncio.run(main())