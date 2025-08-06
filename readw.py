#!/usr/bin/env python3

import asyncio
from bacpypes3.debugging import bacpypes_debugging, ModuleLogger
from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.app import Application
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier
from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication

# 로깅 설정
_debug = 0
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
        from bacpypes3.basetypes import EngineeringUnits
        
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
        
        # 열거형 시도 (units 등)
        try:
            enum_val = bacnet_value.cast_out(Enumerated)
            if enum_val is not None:
                return int(enum_val)
        except:
            pass
        
        # EngineeringUnits 시도
        try:
            units_val = bacnet_value.cast_out(EngineeringUnits)
            if units_val is not None:
                # 단위 번호를 단위 이름으로 변환
                units_map = {
                    95: "degrees-celsius",
                    96: "degrees-fahrenheit", 
                    98: "degrees-kelvin",
                    5: "amperes",
                    4: "volts",
                    74: "kilowatts",
                    19: "cubic-feet-per-minute",
                    159: "no-units",
                    62: "percent",
                    # 더 많은 단위들...
                }
                return units_map.get(int(units_val), f"unit-{int(units_val)}")
        except:
            pass
        
        # 원시 데이터 접근 시도
        try:
            if hasattr(bacnet_value, 'tagList') and bacnet_value.tagList:
                tag = bacnet_value.tagList[0]
                if hasattr(tag, 'tagData'):
                    # 바이트 데이터를 적절히 변환
                    if len(tag.tagData) == 1:
                        return int.from_bytes(tag.tagData, 'big')
                    elif len(tag.tagData) == 2:
                        return int.from_bytes(tag.tagData, 'big')
                    elif len(tag.tagData) == 4:
                        # 4바이트는 float일 수도 있음
                        import struct
                        try:
                            return struct.unpack('>f', tag.tagData)[0]
                        except:
                            return int.from_bytes(tag.tagData, 'big')
        except:
            pass
        
        # 직접 문자열 변환
        return str(bacnet_value)
        
    except Exception as e:
        print(f"값 추출 오류: {e}")
        return str(bacnet_value)

def debug_any_object(any_obj, name="Unknown"):
    """Any 객체의 구조를 디버깅"""
    print(f"\n=== Debug {name} ===")
    print(f"Type: {type(any_obj)}")
    print(f"Dir: {[attr for attr in dir(any_obj) if not attr.startswith('_')]}")
    
    # 중요한 속성들 확인
    important_attrs = ['value', 'tagList', 'cast_out', 'encode', 'decode']
    for attr in important_attrs:
        if hasattr(any_obj, attr):
            try:
                val = getattr(any_obj, attr)
                print(f"{attr}: {val} (type: {type(val)})")
            except Exception as e:
                print(f"{attr}: Error - {e}")
    
    # tagList가 있다면 상세 확인
    if hasattr(any_obj, 'tagList') and any_obj.tagList:
        print("TagList details:")
        for i, tag in enumerate(any_obj.tagList):
            print(f"  Tag {i}: {tag}")
            if hasattr(tag, 'tagData'):
                print(f"    tagData: {tag.tagData} (hex: {tag.tagData.hex() if tag.tagData else 'None'})")
            if hasattr(tag, 'tagClass'):
                print(f"    tagClass: {tag.tagClass}")
            if hasattr(tag, 'tagNumber'):
                print(f"    tagNumber: {tag.tagNumber}")
    
    print("=================\n")

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
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean, Enumerated
        from bacpypes3.constructeddata import Any
        
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
        
        # 우선순위 설정 (있는 경우) - priority 필드 사용
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

async def write_present_value(app, device_address, object_id, value, priority=16):
    """Present Value 전용 쓰기 함수 (우선순위 포함)"""
    try:
        from bacpypes3.primitivedata import Real, Unsigned, CharacterString, Boolean
        from bacpypes3.constructeddata import Any
        
        # 값 타입 자동 결정
        if isinstance(value, float):
            bacnet_value = Any(Real(value))
        elif isinstance(value, int):
            bacnet_value = Any(Unsigned(value))
        elif isinstance(value, bool):
            bacnet_value = Any(Boolean(value))
        else:
            bacnet_value = Any(CharacterString(str(value)))
        
        # WritePropertyRequest with priority
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier="presentValue",
            propertyValue=bacnet_value
        )
        
        # 우선순위 설정
        if priority is not None:
            request.priority = priority
            
        request.pduDestination = Address(device_address)
        
        response = await app.request(request)
        
        if response:
            print(f"Present Value 쓰기 성공: {object_id} = {value} (priority: {priority})")
            return True
        else:
            print("Present Value 쓰기 실패")
            return False
            
    except Exception as e:
        print(f"Present Value 쓰기 오류: {e}")
        return False

async def safe_write_test(app, device_address):
    """안전한 쓰기 테스트 - 여러 객체 타입 시도"""
    print("=== 안전한 쓰기 테스트 ===")
    
    # 쓰기 가능한 객체 타입들 (우선순위 순)
    writable_objects = [
        ("analogValue", 1),
        ("analogValue", 2), 
        ("analogOutput", 1),
        ("analogOutput", 2),
        ("binaryValue", 1),
        ("multiStateValue", 1)
    ]
    
    test_values = {
        "analog": 42.5,
        "binary": True,
        "multiState": 2
    }
    
    for obj_id in writable_objects:
        obj_type = obj_id[0]
        print(f"\n시도 중: {obj_id}")
        
        try:
            # 먼저 객체가 존재하는지 확인 (objectName 읽기)
            name = await read_property(app, device_address, obj_id, "objectName")
            if name and "Any object" not in str(name):
                print(f"  객체 발견: {name}")
                
                # 적절한 테스트 값 선택
                if "analog" in obj_type:
                    test_val = test_values["analog"]
                elif "binary" in obj_type:
                    test_val = test_values["binary"]
                elif "multiState" in obj_type:
                    test_val = test_values["multiState"]
                else:
                    test_val = test_values["analog"]
                
                # 쓰기 시도
                success = await write_present_value(app, device_address, obj_id, test_val)
                if success:
                    # 확인
                    await asyncio.sleep(0.5)
                    new_val = await read_property(app, device_address, obj_id, "presentValue")
                    print(f"  쓰기 성공: {test_val} → 읽은 값: {new_val}")
                    return obj_id, test_val  # 성공한 객체 반환
                else:
                    print(f"  쓰기 실패")
            else:
                print(f"  객체 없음 또는 접근 불가")
                
        except Exception as e:
            print(f"  오류: {e}")
            
    print("모든 쓰기 시도 실패")
    return None, None

async def main():
    """메인 함수"""
    try:
        # 디바이스 객체 생성
        device = DeviceObject(
            objectName="BACpypes3 Reader",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        # NormalApplication 사용 (올바른 애플리케이션 클래스)
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        print("=== BACpypes3 읽기 예제 ===")
        print("애플리케이션 시작됨")
        print(f"로컬 주소: 200.0.0.234")
        print(f"타겟 디바이스: 200.0.0.162")
        
        # 예제 1: Present Value 읽기
        device_address = "200.0.0.162"
        object_id = ("analogInput", 1)
        property_id = "presentValue"
        
        print(f"\n읽기 시도: {device_address}")
        print(f"객체: {object_id}, 속성: {property_id}")
        
        value = await read_property(app, device_address, object_id, property_id)
        
        if value is not None:
            print(f"읽은 값: {value}")
        else:
            print("값을 읽을 수 없습니다.")
        
        # 예제 2: 객체 이름 읽기
        print("\n--- 객체 이름 읽기 ---")
        name_value = await read_property(app, device_address, object_id, "objectName")
        if name_value is not None:
            print(f"객체 이름: {name_value}")
        
        # 예제 3: 여러 속성 읽기
        print("\n--- 여러 속성 읽기 ---")
        properties = ["presentValue", "objectName", "description", "units"]
        
        for prop in properties:
            print(f"읽는 중: {prop}")
            value = await read_property(app, device_address, object_id, prop)
            print(f"{prop}: {value}")
            
            # units 속성인 경우 상세 디버깅
            if prop == "units" and isinstance(value, str) and "Any object" in value:
                # 원본 응답 다시 가져와서 디버깅
                debug_request = ReadPropertyRequest(
                    objectIdentifier=ObjectIdentifier(object_id),
                    propertyIdentifier=prop
                )
                debug_request.pduDestination = Address(device_address)
                debug_response = await app.request(debug_request)
                if debug_response:
                    debug_any_object(debug_response.propertyValue, f"{prop} value")
            
            await asyncio.sleep(0.5)  # 요청 간격
            
    except KeyboardInterrupt:
        print("\n프로그램 중단됨")
    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()

# 더 간단한 사용 예제
async def simple_read():
    """간단한 읽기 예제"""
    try:
        # 기본 설정으로 디바이스 생성
        device = DeviceObject(
            objectName="Simple Reader",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        # NormalApplication 사용
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        print("간단한 읽기 시작...")
        print(f"로컬: 200.0.0.234 → 타겟: 200.0.0.162")
        
        # 읽기 실행
        target_device = "200.0.0.162"
        object_id = ("analogInput", 1)
        
        value = await read_property(app, target_device, object_id, "presentValue")
        print(f"Present Value: {value}")
        
        # 디버깅: 원본 객체 타입도 확인
        debug_request = ReadPropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier="presentValue"
        )
        debug_request.pduDestination = Address(target_device)
        
        raw_response = await app.request(debug_request)
        if raw_response:
            raw_value = raw_response.propertyValue
            print(f"Raw Value Type: {type(raw_value)}")
            print(f"Raw Value Dir: {[attr for attr in dir(raw_value) if not attr.startswith('_')]}")
        
        # 디바이스 이름도 읽어보기
        device_name = await read_property(app, target_device, ("device", 162), "objectName")
        print(f"Device Name: {device_name}")
        
        # === 쓰기 테스트 ===
        print("\n=== 쓰기 테스트 ===")
        
        # 안전한 쓰기 테스트 먼저 시도
        writable_obj, test_val = await safe_write_test(app, target_device)
        
        if writable_obj:
            print(f"\n쓰기 가능한 객체 발견: {writable_obj}")
            
            # 추가 테스트
            print("\n추가 쓰기 테스트:")
            values_to_test = [10.0, 20.5, 30.0] if "analog" in writable_obj[0] else [True, False, True]
            
            for val in values_to_test:
                success = await write_present_value(app, target_device, writable_obj, val)
                if success:
                    await asyncio.sleep(0.5)
                    read_val = await read_property(app, target_device, writable_obj, "presentValue")
                    print(f"  {val} → {read_val}")
                await asyncio.sleep(1)
        else:
            print("쓰기 가능한 객체를 찾을 수 없습니다.")
            print("가능한 원인:")
            print("1. 대상 디바이스에 쓰기 가능한 객체가 없음")
            print("2. 쓰기 권한이 없음")
            print("3. 네트워크 연결 문제")
        
    except Exception as e:
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()

# 배치 쓰기 함수
async def batch_write(app, device_address, write_list):
    """여러 속성을 순차적으로 쓰기"""
    results = {}
    
    for object_id, property_id, value in write_list:
        key = f"{object_id[0]}:{object_id[1]}.{property_id}"
        try:
            print(f"쓰는 중: {key} = {value}")
            success = await write_property(app, device_address, object_id, property_id, value)
            results[key] = "성공" if success else "실패"
            await asyncio.sleep(0.5)  # 요청 간격
        except Exception as e:
            results[key] = f"오류: {e}"
    
    return results

# 쓰기 전용 예제
async def write_example():
    """쓰기 전용 예제"""
    try:
        device = DeviceObject(
            objectName="BACnet Writer",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        print("=== BACnet 쓰기 예제 ===")
        print(f"로컬: 200.0.0.234 → 타겟: 200.0.0.162")
        
        target_device = "200.0.0.162"
        object_id = ("analogOutput", 1)  # 쓰기 가능한 객체
        
        # 1. Present Value 쓰기 (우선순위 포함)
        print("\n1. Present Value 쓰기")
        values_to_write = [10.0, 20.5, 30.25]
        
        for val in values_to_write:
            print(f"값 {val} 쓰기 중...")
            success = await write_present_value(app, target_device, object_id, val, priority=16)
            if success:
                await asyncio.sleep(1)
                read_val = await read_property(app, target_device, object_id, "presentValue")
                print(f"확인: {read_val}")
            await asyncio.sleep(2)
        
        # 2. 배치 쓰기
        print("\n2. 배치 쓰기")
        write_list = [
            (("analogOutput", 1), "presentValue", 50.0),
            (("analogOutput", 1), "description", "Updated by BACpypes3"),
            (("analogOutput", 2), "presentValue", 75.5),
        ]
        
        results = await batch_write(app, target_device, write_list)
        
        print("\n배치 쓰기 결과:")
        for name, result in results.items():
            print(f"{name}: {result}")
            
        # 3. 쓰기 후 전체 확인
        print("\n3. 쓰기 결과 확인")
        verify_list = [
            (("analogOutput", 1), "presentValue"),
            (("analogOutput", 1), "description"),
            (("analogOutput", 2), "presentValue"),
        ]
        
        for obj_id, prop_id in verify_list:
            value = await read_property(app, target_device, obj_id, prop_id)
            print(f"{obj_id[0]}:{obj_id[1]}.{prop_id} = {value}")
            
    except Exception as e:
        print(f"쓰기 예제 오류: {e}")
        import traceback
        traceback.print_exc()
async def batch_read_sequential(app, device_address, read_list):
    """여러 속성을 순차적으로 읽기"""
    results = {}
    
    for object_id, property_id in read_list:
        key = f"{object_id[0]}:{object_id[1]}.{property_id}"
        try:
            print(f"읽는 중: {key}")
            value = await read_property(app, device_address, object_id, property_id)
            results[key] = value
            await asyncio.sleep(0.1)  # 요청 간격
        except Exception as e:
            results[key] = f"오류: {e}"
    
    return results

# 배치 읽기 예제
async def batch_example():
    """배치 읽기 예제"""
    try:
        device = DeviceObject(
            objectName="Batch Reader",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        # 읽을 목록 정의
        read_list = [
            (("analogInput", 1), "presentValue"),
            (("analogInput", 1), "objectName"),
            (("analogInput", 1), "description"),
            (("device", 162), "objectName"),  # 타겟 디바이스 162의 이름
        ]
        
        print("=== 배치 읽기 시작 ===")
        print(f"로컬: 200.0.0.234 → 타겟: 200.0.0.162")
        results = await batch_read_sequential(app, "200.0.0.162", read_list)
        
        print("\n=== 배치 읽기 결과 ===")
        for name, value in results.items():
            print(f"{name}: {value}")
            
    except Exception as e:
        print(f"배치 읽기 오류: {e}")
        import traceback
        traceback.print_exc()

# Who-Is 요청 예제 (네트워크의 디바이스 찾기)
async def discover_devices():
    """네트워크에서 BACnet 디바이스 찾기"""
    try:
        from bacpypes3.apdu import WhoIsRequest
        
        device = DeviceObject(
            objectName="Device Discoverer",
            objectIdentifier=("device", 599),
            maxApduLengthAccepted=1024,
            segmentationSupported="segmentedBoth",
            vendorIdentifier=15
        )
        
        local_address = IPv4Address("200.0.0.234/24")
        app = NormalApplication(device, local_address)
        
        print("=== 디바이스 검색 ===")
        print(f"로컬 주소: 200.0.0.234에서 검색 중...")
        
        # Who-Is 요청 (브로드캐스트)
        request = WhoIsRequest()
        request.pduDestination = Address()  # 브로드캐스트
        
        print("Who-Is 요청 전송 중...")
        
        # 주의: Who-Is는 응답을 기다리지 않고 I-Am 메시지를 받아야 함
        # 실제 구현에서는 I-Am 핸들러가 필요함
        
    except Exception as e:
        print(f"디바이스 검색 오류: {e}")

if __name__ == "__main__":
    print("BACpypes3 수정된 버전")
    print("pip install bacpypes3")
    print()
    
    print("실행 옵션:")
    print("1. asyncio.run(main())              # 전체 예제 (읽기+쓰기)")
    print("2. asyncio.run(simple_read())       # 간단한 읽기") 
    print("3. asyncio.run(batch_example())     # 배치 읽기")
    print("4. asyncio.run(write_example())     # 쓰기 전용 예제")
    print("5. asyncio.run(discover_devices())  # 디바이스 검색")
    print()
    print("주의사항:")
    print("- 로컬 주소: 200.0.0.234/24")
    print("- 타겟 디바이스: 200.0.0.162")
    print("- 디바이스 ID: 162 (필요시 수정)")
    print("- 방화벽에서 UDP 47808 포트를 허용하세요")
    print("- 네트워크 연결 상태를 확인하세요")
    
    # 기본 실행
    asyncio.run(main())