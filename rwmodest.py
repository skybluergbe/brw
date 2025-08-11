#!/usr/bin/env python3

import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real, Unsigned
from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.constructeddata import Any

# 디버깅 비활성화
_debug = 0

def extract_value(bacnet_value):
    """BACnet Any 객체에서 실제 값 추출 (multiState 지원 버전)"""
    if bacnet_value is None:
        return None
    
    try:
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean, Enumerated
        
        # 정수형(multiState) 시도
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

async def write_property(app, device_address, object_id, property_id, value, priority=None):
    """BACnet 속성 쓰기 함수"""
    try:
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean
        
        # 값의 타입에 따라 적절한 BACnet 타입으로 변환
        if isinstance(value, float):
            bacnet_value = Any(Real(value))
        elif isinstance(value, int):
            bacnet_value = Any(Unsigned(value))  # multiState는 정수로 처리
        elif isinstance(value, str):
            bacnet_value = Any(CharacterString(value))
        elif isinstance(value, bool):
            bacnet_value = Any(Boolean(value))
        else:
            bacnet_value = Any(CharacterString(str(value)))
        
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
        return False

async def read_multistate_info(app, device_address, object_id):
    """multiStateValue 객체의 상태 텍스트 목록 읽기"""
    try:
        # 상태 텍스트 목록 읽기
        state_texts = await read_property(app, device_address, object_id, "stateText")
        if state_texts:
            print(f"상태 텍스트: {state_texts}")
            return state_texts
        else:
            # 상태 텍스트를 읽을 수 없는 경우 값 목록 읽기 시도
            number_of_states = await read_property(app, device_address, object_id, "numberOfStates")
            if number_of_states:
                print(f"상태 수: {number_of_states}")
                return [f"상태 {i}" for i in range(1, int(number_of_states) + 1)]
            else:
                print("상태 정보를 읽을 수 없습니다.")
                return None
    except Exception as e:
        print(f"상태 정보 읽기 오류: {e}")
        return None

async def manage_multistate_value(target_device, object_id, new_state=None):
    """multiStateValue 객체 읽기 및 쓰기"""
    try:
        # 기본 디바이스 설정
        device = DeviceObject(
            objectName="BACnet MultiState Manager",
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
        
        # 객체 이름 읽기
        object_name = await read_property(app, target_device, object_id, "objectName")
        if object_name:
            print(f"객체 이름: {object_name}")
        else:
            print("객체 이름을 읽을 수 없습니다.")
        
        # 현재 상태 읽기
        current_state = await read_property(app, target_device, object_id, "presentValue")
        
        # 상태 텍스트 정보 읽기
        state_info = await read_multistate_info(app, target_device, object_id)
        
        if current_state is not None:
            state_text = f"상태 {current_state}"
            if state_info and isinstance(state_info, list) and 0 < int(current_state) <= len(state_info):
                state_text = f"{state_text} ({state_info[int(current_state)-1]})"
            
            print(f"현재 상태: {state_text}")
        else:
            print("현재 상태를 읽을 수 없습니다.")
        
        # 새 상태 쓰기 (지정된 경우)
        if new_state is not None:
            print(f"\n새 상태 ({new_state}) 쓰기 중...")
            
            # 우선순위 16으로 쓰기
            success = await write_property(app, target_device, object_id, "presentValue", new_state, priority=16)
            
            if success:
                print(f"성공: {object_id}.presentValue = {new_state} (우선순위: 16)")
                
                # 확인을 위해 다시 읽기
                await asyncio.sleep(0.5)
                updated_state = await read_property(app, target_device, object_id, "presentValue")
                
                if updated_state is not None:
                    state_text = f"상태 {updated_state}"
                    if state_info and isinstance(state_info, list) and 0 < int(updated_state) <= len(state_info):
                        state_text = f"{state_text} ({state_info[int(updated_state)-1]})"
                    
                    print(f"확인된 상태: {state_text}")
                    
                    # 값이 제대로 설정되었는지 확인
                    if int(updated_state) == int(new_state):
                        print("✓ 상태가 성공적으로 변경되었습니다.")
                    else:
                        print(f"! 상태가 다릅니다. 예상: {new_state}, 실제: {updated_state}")
                else:
                    print("확인 상태를 읽을 수 없습니다.")
            else:
                print("실패: 응답 없음")
        
        return True
    
    except Exception as e:
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 함수"""
    # 설정값
    target_device = "200.0.0.162"
    object_id = ("multiStateValue", 1)  # multiStateValue 객체
    new_state = 2  # 설정할 새 상태 (1, 2, 3 등)
    
    # 주석 처리하면 읽기만 수행
    # new_state = None
    
    # 실행
    await manage_multistate_value(target_device, object_id, new_state)

if __name__ == "__main__":
    print("BACnet MultiState 값 관리 도구")
    print("===========================")
    asyncio.run(main())