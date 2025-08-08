#!/usr/bin/env python3

import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real
from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.constructeddata import Any

# 디버깅 비활성화
_debug = 0

def extract_value(bacnet_value):
    """BACnet Any 객체에서 실제 값 추출 (간소화 버전)"""
    if bacnet_value is None:
        return None
    
    try:
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean
        
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

async def read_property(app, device_address, object_id, property_id):
    """BACnet 속성 읽기 함수"""
    try:
        request = ReadPropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier=property_id
        )
        request.pduDestination = Address(device_address)
        
        response = await app.request(request)
        if response:
            return extract_value(response.propertyValue)
        else:
            return None
    except Exception as e:
        print(f"읽기 오류 ({object_id}.{property_id}): {e}")
        return None

async def write_single_value(target_device, object_id, property_id, value, priority=16):
    """단순화된 단일 값 쓰기 함수"""
    try:
        # 기본 디바이스 설정
        device = DeviceObject(
            objectName="BACnet Writer",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        # 애플리케이션 생성
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        print(f"타겟 디바이스: {target_device}")
        print(f"객체: {object_id}, 속성: {property_id}")
        print(f"설정 값: {value}, 우선순위: {priority}")
        
        # 객체 이름 읽기
        object_name = await read_property(app, target_device, object_id, "objectName")
        if object_name:
            print(f"객체 이름: {object_name}")
        else:
            print("객체 이름을 읽을 수 없습니다.")
        
        # 현재 값 읽기
        current_value = await read_property(app, target_device, object_id, property_id)
        if current_value is not None:
            print(f"현재 값: {current_value}")
        else:
            print("현재 값을 읽을 수 없습니다.")
        
        # 새 값 쓰기
        print(f"\n새 값 쓰기 중...")
        
        # 실수값을 BACnet 형식으로 변환
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
            
        request.pduDestination = Address(target_device)
        
        # 요청 전송
        response = await app.request(request)
        
        if response:
            print(f"성공: {object_id}.{property_id} = {value} (우선순위: {priority})")
            
            # 확인을 위해 다시 읽기
            await asyncio.sleep(0.5)  # 잠시 대기
            new_value = await read_property(app, target_device, object_id, property_id)
            
            if new_value is not None:
                print(f"확인된 값: {new_value}")
                
                # 값이 제대로 설정되었는지 확인
                if float(new_value) == float(value):
                    print("✓ 값이 성공적으로 변경되었습니다.")
                else:
                    print(f"! 값이 다릅니다. 예상: {value}, 실제: {new_value}")
            else:
                print("확인 값을 읽을 수 없습니다.")
            
            return True
        else:
            print("실패: 응답 없음")
            return False
            
    except Exception as e:
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 함수"""
    # 설정값
    target_device = "200.0.0.162"
    object_id = ("analogOutput", 1)
    property_id = "presentValue"
    value = 42.5
    priority = 16
    
    # 쓰기 실행
    await write_single_value(target_device, object_id, property_id, value, priority)

if __name__ == "__main__":
    print("BACnet 단일 값 쓰기 도구 (간소화 버전)")
    print("===============================")
    asyncio.run(main())