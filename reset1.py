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

async def attempt_null_write(target_device, object_id, priority=8):
    """NULL 값 쓰기 시도 함수"""
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
        
        # 우선순위 배열 읽기
        print("\n현재 우선순위 배열:")
        for i in range(1, 17):
            priority_value_raw = await read_property(app, target_device, object_id, "priorityArray", i)
            priority_value = extract_value(priority_value_raw)
            print(f"  우선순위 {i}: {priority_value}")
        
        # 방법 1: Real(0)으로 값 설정 후 확인
        print("\n방법 1: Real(0) 값 설정")
        await write_property(app, target_device, object_id, "presentValue", 0.0, priority)
        
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
        
        # 방법 2: NULL 값 쓰기 (여러 방법 시도)
        print("\n방법 2: NULL 값 쓰기 시도")
        
        # 방법 2-1: 빈 Any 객체 시도
        try:
            print("\n2-1: 빈 Any 객체 시도")
            
            # 빈 Any 객체 생성
            empty_any = Any()
            
            # 쓰기 요청 생성
            request = WritePropertyRequest(
                objectIdentifier=ObjectIdentifier(object_id),
                propertyIdentifier="presentValue",
                propertyValue=empty_any
            )
            
            # 우선순위 설정
            request.priority = priority
            request.pduDestination = Address(target_device)
            
            # 요청 전송
            response = await app.request(request)
            
            if response:
                print(f"성공: 빈 Any 객체로 {object_id}.presentValue 우선순위 {priority} 설정됨")
                
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
            else:
                print("실패: 빈 Any 객체 시도")
        except Exception as e:
            print(f"오류 (빈 Any 객체): {e}")
        
        # 방법 2-2: NULL 구조체 시도
        try:
            print("\n2-2: NULL 구조체 시도")
            
            # BACnet NULL 구조체 생성
            from bacpypes3.primitivedata import Null
            
            try:
                null_value = Null()
            except Exception as e:
                print(f"Null() 생성 오류: {e}")
                null_value = None
            
            if null_value:
                # 쓰기 요청 생성
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
                    print(f"성공: NULL 구조체로 {object_id}.presentValue 우선순위 {priority} 설정됨")
                    
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
                else:
                    print("실패: NULL 구조체 시도")
        except Exception as e:
            print(f"오류 (NULL 구조체): {e}")
        
        # 방법 2-3: 빈 태그 리스트 시도
        try:
            print("\n2-3: 빈 태그 리스트 시도")
            
            # 빈 태그 리스트 생성 시도
            try:
                from bacpypes3.pdu import TagList
                tag_list = TagList()
                
                # Any 객체에 빈 태그 리스트 설정
                property_value = Any()
                property_value.tag_list = tag_list
                
                # 쓰기 요청 생성
                request = WritePropertyRequest(
                    objectIdentifier=ObjectIdentifier(object_id),
                    propertyIdentifier="presentValue",
                    propertyValue=property_value
                )
                
                # 우선순위 설정
                request.priority = priority
                request.pduDestination = Address(target_device)
                
                # 요청 전송
                response = await app.request(request)
                
                if response:
                    print(f"성공: 빈 태그 리스트로 {object_id}.presentValue 우선순위 {priority} 설정됨")
                    
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
                else:
                    print("실패: 빈 태그 리스트 시도")
            except ImportError:
                print("TagList를 가져올 수 없음")
        except Exception as e:
            print(f"오류 (빈 태그 리스트): {e}")
            
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
    priority = 1
    
    # NULL 값 쓰기 시도
    await attempt_null_write(target_device, object_id, priority)

if __name__ == "__main__":
    print("BACnet AnalogOutput NULL 값 쓰기 테스트")
    print("===================================")
    asyncio.run(main())