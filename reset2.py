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

async def write_null_with_tag(app, device_address, object_id, priority):
    """Tag 클래스를 사용하여 NULL 값 쓰기"""
    try:
        from bacpypes3.pdu import Tag, TagClass, TagNumber
        
        # NULL 태그 생성
        null_tag = Tag(TagClass.application, TagNumber.null, b'')
        
        # Any 객체에 태그 설정 시도
        property_value = Any()
        property_value.tag = null_tag
        
        # 쓰기 요청 생성
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier="presentValue",
            propertyValue=property_value
        )
        
        # 우선순위 설정
        request.priority = priority
        request.pduDestination = Address(device_address)
        
        # 요청 전송
        response = await app.request(request)
        return response is not None
    except Exception as e:
        print(f"Tag를 사용한 NULL 쓰기 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def relinquish_default(app, device_address, object_id):
    """relinquishDefault 값 읽기"""
    try:
        relinquish_default_raw = await read_property(app, device_address, object_id, "relinquishDefault")
        relinquish_default = extract_value(relinquish_default_raw)
        print(f"relinquishDefault 값: {relinquish_default}")
        return relinquish_default
    except Exception as e:
        print(f"relinquishDefault 읽기 오류: {e}")
        return None

async def try_null_write_methods(target_device, object_id, priority=8):
    """다양한 NULL 값 쓰기 방법 시도"""
    try:
        # 기본 디바이스 설정
        device = DeviceObject(
            objectName="BACnet NULL Writer",
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
        
        # relinquishDefault 값 읽기
        await relinquish_default(app, target_device, object_id)
        
        # 우선순위 배열 읽기
        print("\n현재 우선순위 배열:")
        for i in range(1, 17):
            priority_value_raw = await read_property(app, target_device, object_id, "priorityArray", i)
            priority_value = extract_value(priority_value_raw)
            print(f"  우선순위 {i}: {priority_value}")
        
        # ====== NULL 값 쓰기 시도 ======
        print("\n===== NULL 값 쓰기 시도 =====")
        
        # 방법 1: Tag 클래스 사용
        print("\n방법 1: Tag 클래스 사용")
        success1 = await write_null_with_tag(app, target_device, object_id, priority)
        
        if success1:
            print(f"성공: Tag 클래스로 {object_id}.presentValue 우선순위 {priority} NULL 설정됨")
            
            # 확인
            await asyncio.sleep(0.5)
            current_value_raw = await read_property(app, target_device, object_id, "presentValue")
            current_value = extract_value(current_value_raw)
            print(f"설정 후 값: {current_value}")
            
            # 우선순위 배열 확인
            print("\n설정 후 우선순위 배열:")
            for i in range(1, 17):
                priority_value_raw = await read_property(app, target_device, object_id, "priorityArray", i)
                priority_value = extract_value(priority_value_raw)
                print(f"  우선순위 {i}: {priority_value}")
                
            return True
        else:
            print("방법 1 실패")
        
        # 방법 2: 먼저 실수 값을 쓴 다음 다른 방법 시도
        print("\n방법 2: 먼저 실수 값을 쓴 다음 시도")
        
        # 실수 값 쓰기
        await write_property(app, target_device, object_id, "presentValue", 0.0, priority)
        
        # 확인
        await asyncio.sleep(0.5)
        current_value_raw = await read_property(app, target_device, object_id, "presentValue")
        current_value = extract_value(current_value_raw)
        print(f"0.0 설정 후 값: {current_value}")
        
        # 우선순위 배열 확인
        print("\n0.0 설정 후 우선순위 배열:")
        for i in range(1, 17):
            priority_value_raw = await read_property(app, target_device, object_id, "priorityArray", i)
            priority_value = extract_value(priority_value_raw)
            print(f"  우선순위 {i}: {priority_value}")
        
        # 이제 다른 NULL 값 쓰기 방법 시도
        
        # 방법 2-1: 로우 레벨 방식 시도
        try:
            print("\n방법 2-1: 로우 레벨 방식 시도")
            
            # 빈 WritePropertyRequest 생성
            request = WritePropertyRequest(
                objectIdentifier=ObjectIdentifier(object_id),
                propertyIdentifier="presentValue"
            )
            
            # NULL 값 직접 처리
            from bacpypes3.pdu import Tag, TagClass, TagNumber
            
            # NULL 태그 생성 및 설정
            null_tag = Tag(TagClass.application, TagNumber.null, b'')
            
            # 수동으로 태그 목록 생성
            tags = []
            # 태그 0: 컨텍스트 태그 (opening)
            tags.append(Tag(TagClass.context, 4, b'', True))
            # 태그 1: 값 (NULL)
            tags.append(null_tag)
            # 태그 2: 컨텍스트 태그 (closing)
            tags.append(Tag(TagClass.context, 4, b'', False))
            
            # 태그를 직접 요청에 설정
            request._value = tags
            
            # 우선순위 설정
            request.priority = priority
            request.pduDestination = Address(target_device)
            
            # 요청 전송
            response = await app.request(request)
            
            if response:
                print(f"방법 2-1 성공: {object_id}.presentValue 우선순위 {priority} NULL 설정됨")
                
                # 확인
                await asyncio.sleep(0.5)
                current_value_raw = await read_property(app, target_device, object_id, "presentValue")
                current_value = extract_value(current_value_raw)
                print(f"설정 후 값: {current_value}")
                
                # 우선순위 배열 확인
                print("\n설정 후 우선순위 배열:")
                for i in range(1, 17):
                    priority_value_raw = await read_property(app, target_device, object_id, "priorityArray", i)
                    priority_value = extract_value(priority_value_raw)
                    print(f"  우선순위 {i}: {priority_value}")
                    
                return True
            else:
                print("방법 2-1 실패")
        except Exception as e:
            print(f"방법 2-1 오류: {e}")
            import traceback
            traceback.print_exc()
        
        # 방법 2-2: 예외 처리를 통해 시도
        try:
            print("\n방법 2-2: 예외 처리를 통해 시도")
            
            # Null 값 직접 할당 시도
            from bacpypes3.primitivedata import Null
            
            try:
                # WritePropertyRequest 생성
                request = WritePropertyRequest(
                    objectIdentifier=ObjectIdentifier(object_id),
                    propertyIdentifier="presentValue"
                )
                
                # NULL 값 설정 시도 (직접 Any 구조 사용)
                request.propertyValue = Any()
                request.propertyValue._value = Null()
                
                # 우선순위 설정
                request.priority = priority
                request.pduDestination = Address(target_device)
                
                # 요청 전송
                response = await app.request(request)
                
                if response:
                    print(f"방법 2-2 성공: {object_id}.presentValue 우선순위 {priority} NULL 설정됨")
                    
                    # 확인
                    await asyncio.sleep(0.5)
                    current_value_raw = await read_property(app, target_device, object_id, "presentValue")
                    current_value = extract_value(current_value_raw)
                    print(f"설정 후 값: {current_value}")
                    
                    # 우선순위 배열 확인
                    print("\n설정 후 우선순위 배열:")
                    for i in range(1, 17):
                        priority_value_raw = await read_property(app, target_device, object_id, "priorityArray", i)
                        priority_value = extract_value(priority_value_raw)
                        print(f"  우선순위 {i}: {priority_value}")
                        
                    return True
                else:
                    print("방법 2-2 실패")
            except Exception as e:
                print(f"방법 2-2 내부 오류: {e}")
        except Exception as e:
            print(f"방법 2-2 오류: {e}")
        
        # 방법 3: BACnet 명세에 따라 NULL 표현
        try:
            print("\n방법 3: BACnet 명세에 따라 NULL 표현")
            
            # WritePropertyRequest 생성
            request = WritePropertyRequest(
                objectIdentifier=ObjectIdentifier(object_id),
                propertyIdentifier="presentValue"
            )
            
            # 우선순위 설정
            request.priority = priority
            request.pduDestination = Address(target_device)
            
            # NULL 값 설정 (빈 값 설정)
            request.propertyValue = Any()
            
            # 요청 전송
            response = await app.request(request)
            
            if response:
                print(f"방법 3 성공: {object_id}.presentValue 우선순위 {priority} NULL 설정됨")
                
                # 확인
                await asyncio.sleep(0.5)
                current_value_raw = await read_property(app, target_device, object_id, "presentValue")
                current_value = extract_value(current_value_raw)
                print(f"설정 후 값: {current_value}")
                
                # 우선순위 배열 확인
                print("\n설정 후 우선순위 배열:")
                for i in range(1, 17):
                    priority_value_raw = await read_property(app, target_device, object_id, "priorityArray", i)
                    priority_value = extract_value(priority_value_raw)
                    print(f"  우선순위 {i}: {priority_value}")
                    
                return True
            else:
                print("방법 3 실패")
        except Exception as e:
            print(f"방법 3 오류: {e}")
            import traceback
            traceback.print_exc()
        
        return False
        
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
    await try_null_write_methods(target_device, object_id, priority)

if __name__ == "__main__":
    print("BACnet AnalogOutput NULL 값 쓰기 테스트")
    print("===================================")
    asyncio.run(main())