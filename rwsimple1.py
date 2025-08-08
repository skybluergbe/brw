#!/usr/bin/env python3

import asyncio
from bacpypes3.debugging import ModuleLogger
from bacpypes3.app import Application
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean
from bacpypes3.constructeddata import Any

# 로깅 설정
_log = ModuleLogger(globals())

def extract_value(bacnet_value):
    """BACnet Any 객체에서 실제 값 추출"""
    if bacnet_value is None:
        return None
    
    try:
        # 가장 일반적인 방법들 시도
        if hasattr(bacnet_value, 'value'):
            return bacnet_value.value
        
        # 타입별 캐스팅 시도
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean, Enumerated
        
        # 실수형 시도
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
        
        # 불린형 시도
        try:
            bool_val = bacnet_value.cast_out(Boolean)
            if bool_val is not None:
                return bool(bool_val)
        except:
            pass
        
        # 직접 문자열 변환
        return str(bacnet_value)
        
    except Exception as e:
        print(f"값 추출 오류: {e}")
        return str(bacnet_value)

async def read_property(app, device_address, object_id, property_id):
    """BACnet 디바이스에서 속성 읽기"""
    try:
        # ReadPropertyRequest 생성
        request = ReadPropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier=property_id
        )
        request.pduDestination = Address(device_address)
        
        # 요청 전송 및 응답 대기
        response = await app.request(request)
        
        if response:
            # Any 객체에서 실제 값 추출
            property_value = response.propertyValue
            return extract_value(property_value)
        else:
            print("응답이 없습니다.")
            return None
            
    except Exception as e:
        print(f"읽기 오류: {e}")
        return None

async def write_property(app, device_address, object_id, property_id, value, priority=None):
    """BACnet 디바이스에 속성 쓰기"""
    try:
        # 값의 타입에 따라 적절한 BACnet 데이터 타입으로 변환
        if isinstance(value, float):
            bacnet_value = Any(Real(value))
        elif isinstance(value, int):
            bacnet_value = Any(Unsigned(value))
        elif isinstance(value, str):
            bacnet_value = Any(CharacterString(value))
        elif isinstance(value, bool):
            bacnet_value = Any(Boolean(value))
        else:
            # 기본값으로 문자열 처리
            bacnet_value = Any(CharacterString(str(value)))
        
        # WritePropertyRequest 생성
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier=property_id,
            propertyValue=bacnet_value
        )
        
        # 우선순위 설정 (있는 경우)
        if priority is not None:
            request.priority = priority
        
        request.pduDestination = Address(device_address)
        
        # 요청 전송 및 응답 대기
        response = await app.request(request)
        
        if response:
            print(f"쓰기 성공: {object_id}.{property_id} = {value}")
            return True
        else:
            print("쓰기 응답이 없습니다.")
            return False
            
    except Exception as e:
        print(f"쓰기 오류: {e}")
        return False

async def write_single_value():
    """단일 값 쓰기 전용 함수"""
    try:
        # 디바이스 객체 생성
        device = DeviceObject(
            objectName="BACnet Single Writer",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        # NormalApplication 사용
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        print("=== BACnet 단일 값 쓰기 ===")
        print(f"로컬: 200.0.0.234 → 타겟: 200.0.0.162")
        
        # 변경할 수 있는 설정 값들
        target_device = "200.0.0.162"
        object_id = ("analogOutput", 1)  # 객체 타입과 인스턴스 번호
        property_id = "presentValue"     # 속성 이름
        value = 42.5                     # 쓸 값
        priority = 16                    # 우선순위 (1-16)
        
        # 쓰기 전 현재 값 읽기
        print(f"\n대상: {object_id}, 속성: {property_id}")
        current_value = await read_property(app, target_device, object_id, property_id)
        print(f"현재 값: {current_value}")
        
        # 새 값 쓰기
        print(f"\n새 값: {value} 쓰기 중... (우선순위: {priority})")
        success = await write_property(app, target_device, object_id, property_id, value, priority)
        
        if success:
            # 값이 제대로 변경되었는지 확인
            await asyncio.sleep(0.5)
            new_value = await read_property(app, target_device, object_id, property_id)
            print(f"\n쓰기 후 확인된 값: {new_value}")
            
            if str(new_value) == str(value):
                print("✓ 값이 성공적으로 변경되었습니다.")
            else:
                print(f"! 값이 다릅니다. 예상: {value}, 실제: {new_value}")
        else:
            print("✗ 쓰기 실패")
            
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("BACnet 단일 값 쓰기 도구")
    print("========================")
    print()
    print("설정:")
    print("- 로컬 주소: 200.0.0.234/24")
    print("- 타겟 디바이스: 200.0.0.162")
    print("- 대상: analogOutput:1.presentValue")
    print("- 우선순위: 16")
    print()
    print("참고: 다른 객체나 값을 변경하려면 스크립트 내의 설정을 수정하세요.")
    print("UDP 포트 47808이 방화벽에서 허용되어 있는지 확인하세요.")
    
    # 실행
    asyncio.run(write_single_value())