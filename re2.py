#!/usr/bin/env python3

import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real, Unsigned, Boolean
from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.constructeddata import Any

# 디버깅 비활성화
_debug = 0

def is_null_value(value):
    """값이 NULL인지 확인"""
    if value is None:
        return True
    return str(value).upper().find("NULL") >= 0

def extract_priority_value(bacnet_value):
    """우선순위 배열 요소에서 값 추출"""
    if bacnet_value is None:
        return "NULL"
    
    # NULL 값 확인
    if is_null_value(bacnet_value):
        return "NULL"
    
    try:
        # BACnet 값 추출 시도
        from bacpypes3.primitivedata import Real, Unsigned, Boolean
        
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
        
        # 불린형 시도
        try:
            bool_val = bacnet_value.cast_out(Boolean)
            if bool_val is not None:
                return bool(bool_val)
        except:
            pass
        
        # 기타 처리 (문자열 표현)
        return str(bacnet_value)
    except:
        return str(bacnet_value)

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

async def write_property(app, device_address, object_id, property_id, value, priority=None):
    """BACnet 속성 쓰기 함수"""
    try:
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean
        
        # 값의 타입에 따라 적절한 BACnet 타입으로 변환
        if isinstance(value, float):
            bacnet_value = Any(Real(value))
        elif isinstance(value, int):
            bacnet_value = Any(Unsigned(value))
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
        import traceback
        traceback.print_exc()
        return False

async def read_state_texts(app, device_address, object_id):
    """multiStateValue 객체의 상태 텍스트 목록 읽기"""
    try:
        # 먼저 상태 수 읽기
        number_of_states_raw = await read_property(app, device_address, object_id, "numberOfStates")
        number_of_states = extract_value(number_of_states_raw)
        
        if not number_of_states:
            print("상태 수를 읽을 수 없습니다.")
            return None
            
        number_of_states = int(number_of_states)
        print(f"상태 수: {number_of_states}")
        
        # 각 상태에 대한 텍스트 읽기
        state_texts = []
        for i in range(1, number_of_states + 1):
            state_text_raw = await read_property(app, device_address, object_id, "stateText", i)
            state_text = extract_value(state_text_raw)
            
            if state_text:
                state_texts.append(state_text)
            else:
                state_texts.append(f"상태 {i}")
                
        print("상태 텍스트 목록:")
        for i, text in enumerate(state_texts, 1):
            print(f"  {i}: {text}")
            
        return state_texts
            
    except Exception as e:
        print(f"상태 텍스트 읽기 오류: {e}")
        return None

async def read_priority_array(app, device_address, object_id):
    """presentValue의 우선순위 배열 읽기 (개선 버전)"""
    try:
        # 우선순위 배열 전체를 읽는 것은 무시하고 각 요소를 개별적으로 읽음
        print("\n우선순위 배열:")
        active_priorities = []
        
        for i in range(1, 17):  # 우선순위는 1-16
            priority_value_raw = await read_property(app, device_address, object_id, "priorityArray", i)
            priority_value = extract_priority_value(priority_value_raw)
            
            if priority_value != "NULL":
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

async def relinquish_priority(app, device_address, object_id, priority):
    """특정 우선순위 해제 (Relinquish)"""
    try:
        print(f"\n== 우선순위 {priority} 해제 시도 ==")
        
        # 1. 원래 방식 - Any(Null()) 사용 - BACpypes3 버전 차이로 인해 작동하지 않을 수 있음
        # from bacpypes3.primitivedata import Null
        # request = WritePropertyRequest(
        #     objectIdentifier=ObjectIdentifier(object_id),
        #     propertyIdentifier="presentValue",
        #     propertyValue=Any(Null())
        # )
        
        # 2. 대체 방식 - BACnet 메시지 직접 구성
        # 메시지 종류에 따라 다르지만, 일반적으로 빈 메시지를 보내는 방식
        from bacpypes3.pdu import TagList, Tag, TagClass, TagNumber
        
        # NULL 값을 나타내는 빈 태그 리스트 생성
        tag_list = TagList()
        
        # 쓰기 요청 생성
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier="presentValue",
            propertyValue=Any(tag_list=tag_list)  # 빈 태그 리스트로 NULL 표현
        )
        
        # 우선순위 설정
        request.priority = priority
        request.pduDestination = Address(device_address)
        
        # 요청 전송
        response = await app.request(request)
        
        if response:
            print(f"성공: {object_id}.presentValue 우선순위 {priority} 해제됨")
            
            # 확인
            await asyncio.sleep(0.5)
            current_value_raw = await read_property(app, device_address, object_id, "presentValue")
            current_value = extract_value(current_value_raw)
            print(f"현재 값: {current_value}")
            
            # 우선순위 배열 확인
            await read_priority_array(app, device_address, object_id)
            
            return True
        else:
            print(f"우선순위 {priority} 해제 실패")
            return False
            
    except Exception as e:
        print(f"우선순위 해제 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def set_override(app, device_address, object_id, method="outOfService", value=None, priority=8):
    """override 상태 설정"""
    try:
        if method == "outOfService":
            # outOfService 속성을 True로 설정 (수동 제어 모드)
            print(f"\n== 'outOfService' 방식으로 override 설정 ==")
            
            # 현재 outOfService 상태 확인
            out_of_service_raw = await read_property(app, device_address, object_id, "outOfService")
            out_of_service = extract_value(out_of_service_raw)
            print(f"현재 outOfService 상태: {out_of_service}")
            
            # True로 설정
            success = await write_property(app, device_address, object_id, "outOfService", True)
            
            if success:
                print(f"성공: {object_id}.outOfService = True")
                
                # 확인
                await asyncio.sleep(0.5)
                out_of_service_raw = await read_property(app, device_address, object_id, "outOfService")
                out_of_service = extract_value(out_of_service_raw)
                print(f"확인된 outOfService 상태: {out_of_service}")
                
                # 값 설정 (지정된 경우)
                if value is not None:
                    print(f"\n새 값 {value} 쓰기 중...")
                    val_success = await write_property(app, device_address, object_id, "presentValue", value)
                    
                    if val_success:
                        print(f"성공: {object_id}.presentValue = {value}")
                        
                        # 확인
                        await asyncio.sleep(0.5)
                        new_value_raw = await read_property(app, device_address, object_id, "presentValue")
                        new_value = extract_value(new_value_raw)
                        print(f"확인된 값: {new_value}")
                    else:
                        print("값 쓰기 실패")
                
                return True
            else:
                print("outOfService 설정 실패")
                return False
                
        elif method == "priority":
            # 우선순위 방식으로 override (일반적으로 8번 우선순위 사용)
            print(f"\n== 우선순위 방식으로 override 설정 ==")
            print(f"우선순위: {priority}, 값: {value}")
            
            success = await write_property(app, device_address, object_id, "presentValue", value, priority)
            
            if success:
                print(f"성공: {object_id}.presentValue = {value} (우선순위: {priority})")
                
                # 확인
                await asyncio.sleep(0.5)
                new_value_raw = await read_property(app, device_address, object_id, "presentValue")
                new_value = extract_value(new_value_raw)
                print(f"확인된 값: {new_value}")
                
                # 우선순위 배열 확인
                await read_priority_array(app, device_address, object_id)
                
                return True
            else:
                print("우선순위 override 설정 실패")
                return False
                
        elif method == "relinquish":
            # 특정 우선순위 해제
            return await relinquish_priority(app, device_address, object_id, priority)
                
        else:
            print(f"지원되지 않는 override 방식: {method}")
            return False
            
    except Exception as e:
        print(f"override 설정 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def restore_normal(app, device_address, object_id, method="outOfService"):
    """정상 상태로 복원"""
    try:
        if method == "outOfService":
            # outOfService 속성을 False로 설정 (자동 제어 모드)
            print(f"\n== 정상 상태로 복원 (outOfService = False) ==")
            success = await write_property(app, device_address, object_id, "outOfService", False)
            
            if success:
                print(f"성공: {object_id}.outOfService = False")
                
                # 확인
                await asyncio.sleep(0.5)
                out_of_service_raw = await read_property(app, device_address, object_id, "outOfService")
                out_of_service = extract_value(out_of_service_raw)
                print(f"확인된 outOfService 상태: {out_of_service}")
                
                return True
            else:
                print("정상 상태 복원 실패")
                return False
                
        elif method == "priority":
            # 수동 우선순위 해제 (특정 우선순위 해제)
            return await relinquish_priority(app, device_address, object_id, 8)
                
        else:
            print(f"지원되지 않는 복원 방식: {method}")
            return False
            
    except Exception as e:
        print(f"정상 상태 복원 오류: {e}")
        return False

async def manage_override(target_device, object_id, action="status", method="priority", value=None, priority=8):
    """override 상태 관리"""
    try:
        # 기본 디바이스 설정
        device = DeviceObject(
            objectName="BACnet Override Manager",
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
        object_name_raw = await read_property(app, target_device, object_id, "objectName")
        object_name = extract_value(object_name_raw)
        if object_name:
            print(f"객체 이름: {object_name}")
        else:
            print("객체 이름을 읽을 수 없습니다.")
        
        # 현재 값 읽기
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        if current_value is not None:
            print(f"현재 값: {current_value}")
        
        # outOfService 상태 읽기
        out_of_service_raw = await read_property(app, target_device, object_id, "outOfService")
        out_of_service = extract_value(out_of_service_raw)
        if out_of_service is not None:
            print(f"outOfService 상태: {out_of_service}")
        
        # 우선순위 배열 읽기
        await read_priority_array(app, target_device, object_id)
        
        # multiStateValue인 경우 상태 텍스트 읽기
        if object_id[0] == "multiStateValue":
            await read_state_texts(app, target_device, object_id)
        
        # 동작 수행
        if action == "set":
            # override 설정
            await set_override(app, target_device, object_id, method, value, priority)
        elif action == "clear":
            # 정상 상태로 복원
            await restore_normal(app, target_device, object_id, method)
        elif action == "relinquish":
            # 특정 우선순위 해제
            await relinquish_priority(app, target_device, object_id, priority)
        
        return True
        
    except Exception as e:
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def direct_relinquish_test(target_device, object_id, priority=8):
    """간단한 relinquish 테스트"""
    try:
        # 기본 디바이스 설정
        device = DeviceObject(
            objectName="BACnet Override Manager",
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
        
        # 간단한 방법 - 빈 태그 리스트 사용
        from bacpypes3.pdu import TagList
        
        # 쓰기 요청 생성
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier="presentValue",
            propertyValue=Any(tag_list=TagList())  # 빈 태그 리스트로 NULL 표현
        )
        
        # 우선순위 설정
        request.priority = priority
        request.pduDestination = Address(target_device)
        
        print(f"\n우선순위 {priority} 해제 중...")
        
        # 요청 전송
        response = await app.request(request)
        
        if response:
            print(f"성공: {object_id}.presentValue 우선순위 {priority} 해제됨")
            
            # 현재 값 확인
            await asyncio.sleep(0.5)
            current_value_raw = await read_property(app, target_device, object_id, "presentValue")
            current_value = extract_value(current_value_raw)
            print(f"현재 값: {current_value}")
            
            # 우선순위 배열 확인
            await read_priority_array(app, target_device, object_id)
            
            return True
        else:
            print("우선순위 해제 실패")
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
    object_id = ("analogOutput", 1)  # 아날로그 출력 객체 또는 ("multiStateValue", 1)
    
    # 우선순위
    priority = 8  # 우선순위 (1-16)
    
    # 간단한 relinquish 테스트 실행
    await direct_relinquish_test(target_device, object_id, priority)

if __name__ == "__main__":
    print("BACnet 우선순위 해제 도구")
    print("========================")
    asyncio.run(main())