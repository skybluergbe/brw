#!/usr/bin/env python3

import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real
from bacpypes3.apdu import WritePropertyRequest, ReadPropertyRequest
from bacpypes3.ipv4.app import NormalApplication

# Null 타입 정의
class NullValue:
    """BACnet NULL 값을 나타내는 클래스"""
    def __init__(self):
        pass
    
    def encode(self):
        # NULL 태그 (0x00)
        return b'\x00'
    
    def __str__(self):
        return "NULL"

async def read_priority_array(app, target_device, target_object, priority):
    """우선순위 배열 읽기"""
    try:
        request = ReadPropertyRequest(
            objectIdentifier=ObjectIdentifier(target_object),
            propertyIdentifier="priorityArray",
            propertyArrayIndex=priority
        )
        request.pduDestination = Address(target_device)
        
        response = await asyncio.wait_for(app.request(request), timeout=5.0)
        
        if response and hasattr(response, 'propertyValue'):
            value = response.propertyValue
            # Null 체크
            if value is None or str(value).upper() == 'NULL':
                return "NULL"
            if hasattr(value, 'value'):
                if value.value is None or str(value.value).upper() == 'NULL':
                    return "NULL"
                return value.value
            else:
                return value
        return None
    except Exception as e:
        return f"오류: {e}"

async def write_null_priority_array():
    """priorityArray에 NULL 쓰기 - 가장 간단한 방법"""
    
    # BACnet 장치 설정
    device = DeviceObject(
        objectName="None Writer",
        objectIdentifier=("device", 599),
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15
    )
    
    # 네트워크 설정
    local_address = IPv4Address("200.0.0.234/24")
    app = NormalApplication(device, local_address)
    
    # 타겟 설정
    target_device = "200.0.0.162"
    target_object = ("analogOutput", 1)
    priority = 1  # 우선순위 1
    
    print("=" * 50)
    print("BACnet priorityArray NULL 쓰기")
    print("=" * 50)
    print(f"타겟: {target_device} - {target_object}")
    print(f"우선순위: {priority}")
    print()
    
    # 현재 상태 확인
    print("현재 상태 확인...")
    current_value = await read_priority_array(app, target_device, target_object, priority)
    print(f"현재 우선순위 {priority} 값: {current_value}")
    print()
    
    if str(current_value) == "NULL":
        print("이미 NULL 상태입니다.")
        return
    
    # NULL 쓰기 시도
    print(f"우선순위 {priority}에 NULL 쓰기 시도...")
    
    try:
        # WritePropertyRequest 생성 - propertyValue 없이
        from bacpypes3.pdu import PDU
        from bacpypes3.primitivedata import TagList, Tag, TagNumber
        
        # 수동으로 WriteProperty 요청 생성
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(target_object),
            propertyIdentifier="priorityArray",
            propertyArrayIndex=priority
        )
        
        # NULL 태그 추가 (태그 번호 8, NULL)
        null_tag = Tag(TagNumber(8), b'')  # NULL 태그
        
        # propertyValue로 NULL 설정
        from bacpypes3.constructeddata import Any
        from bacpypes3.primitivedata import Null
        
        # NULL 값 설정 시도 1: 직접 None 사용
        request.propertyValue = None
        request.pduDestination = Address(target_device)
        
        print("  방법 1: None 값 전송...")
        try:
            response = await asyncio.wait_for(app.request(request), timeout=10.0)
            if response:
                print("  ✅ None 전송 성공")
                await asyncio.sleep(1)
                new_value = await read_priority_array(app, target_device, target_object, priority)
                print(f"  변경 후 값: {new_value}")
                if str(new_value) == "NULL":
                    print("  🎉 성공적으로 NULL로 변경됨!")
                    return
        except Exception as e:
            print(f"  ❌ 방법 1 실패: {e}")
        
        # NULL 값 설정 시도 2: 빈 Any 사용
        print("\n  방법 2: 빈 Any() 전송...")
        request.propertyValue = Any()
        try:
            response = await asyncio.wait_for(app.request(request), timeout=10.0)
            if response:
                print("  ✅ 빈 Any 전송 성공")
                await asyncio.sleep(1)
                new_value = await read_priority_array(app, target_device, target_object, priority)
                print(f"  변경 후 값: {new_value}")
                if str(new_value) == "NULL":
                    print("  🎉 성공적으로 NULL로 변경됨!")
                    return
        except Exception as e:
            print(f"  ❌ 방법 2 실패: {e}")
        
        # NULL 값 설정 시도 3: Real(0.0) 후 재시도
        print("\n  방법 3: 0.0 쓰고 다시 시도...")
        request.propertyValue = Any(Real(0.0))
        try:
            response = await asyncio.wait_for(app.request(request), timeout=10.0)
            if response:
                print("  ✅ 0.0 전송 성공")
                # 바로 None 다시 시도
                request.propertyValue = None
                response = await asyncio.wait_for(app.request(request), timeout=10.0)
                if response:
                    print("  ✅ 후속 None 전송 성공")
                    await asyncio.sleep(1)
                    new_value = await read_priority_array(app, target_device, target_object, priority)
                    print(f"  변경 후 값: {new_value}")
                    if str(new_value) == "NULL":
                        print("  🎉 성공적으로 NULL로 변경됨!")
                        return
        except Exception as e:
            print(f"  ❌ 방법 3 실패: {e}")
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n모든 방법 실패 - 장치가 NULL 쓰기를 지원하지 않을 수 있습니다.")


async def release_priority():
    """우선순위 해제 (Release) - presentValue 사용"""
    
    # BACnet 장치 설정
    device = DeviceObject(
        objectName="Priority Releaser",
        objectIdentifier=("device", 599),
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15
    )
    
    # 네트워크 설정
    local_address = IPv4Address("200.0.0.234/24")
    app = NormalApplication(device, local_address)
    
    # 타겟 설정
    target_device = "200.0.0.162"
    target_object = ("analogOutput", 1)
    
    print("=" * 50)
    print("BACnet 우선순위 해제 (Release)")
    print("=" * 50)
    print(f"타겟: {target_device} - {target_object}")
    print()
    
    priority = int(input("해제할 우선순위 번호 (1-16): "))
    
    if priority < 1 or priority > 16:
        print("잘못된 우선순위 번호입니다.")
        return
    
    print(f"\n우선순위 {priority} 해제 중...")
    
    try:
        # presentValue에 쓰기 (우선순위 지정, 값 없음)
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(target_object),
            propertyIdentifier="presentValue"
        )
        request.priority = priority
        request.pduDestination = Address(target_device)
        
        # propertyValue를 설정하지 않거나 None으로 설정
        request.propertyValue = None
        
        print("  Release 명령 전송 중...")
        response = await asyncio.wait_for(app.request(request), timeout=10.0)
        
        if response:
            print("  ✅ Release 명령 전송 성공")
            
            # 결과 확인
            await asyncio.sleep(1)
            new_value = await read_priority_array(app, target_device, target_object, priority)
            print(f"  변경 후 우선순위 {priority} 값: {new_value}")
            
            if str(new_value) == "NULL":
                print("  🎉 성공적으로 해제되었습니다!")
            else:
                print("  ⚠️ 명령은 성공했지만 값이 변경되지 않았습니다.")
        else:
            print("  ❌ 실패: 응답 없음")
            
    except Exception as e:
        print(f"❌ 오류: {e}")


async def check_all_priorities():
    """모든 우선순위 상태 확인"""
    
    # BACnet 장치 설정
    device = DeviceObject(
        objectName="Priority Checker",
        objectIdentifier=("device", 599),
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15
    )
    
    # 네트워크 설정
    local_address = IPv4Address("200.0.0.234/24")
    app = NormalApplication(device, local_address)
    
    # 타겟 설정
    target_device = "200.0.0.162"
    target_object = ("analogOutput", 1)
    
    print("=" * 50)
    print("모든 우선순위 상태 확인")
    print("=" * 50)
    print(f"타겟: {target_device} - {target_object}")
    print()
    
    active_count = 0
    
    for priority in range(1, 17):
        value = await read_priority_array(app, target_device, target_object, priority)
        
        if str(value) != "NULL" and "오류" not in str(value):
            print(f"우선순위 {priority:2d}: {value} [활성]")
            active_count += 1
        else:
            print(f"우선순위 {priority:2d}: NULL")
    
    print()
    print(f"활성 우선순위 개수: {active_count}/16")


async def main():
    """메인 함수"""
    
    while True:
        print("\n" + "=" * 50)
        print("BACnet 우선순위 NULL 설정 도구")
        print("=" * 50)
        print("1. 우선순위 1에 NULL 쓰기 시도")
        print("2. 우선순위 해제 (Release)")
        print("3. 모든 우선순위 상태 확인")
        print("4. 종료")
        
        choice = input("\n선택 (1/2/3/4): ").strip()
        
        if choice == "1":
            await write_null_priority_array()
        elif choice == "2":
            await release_priority()
        elif choice == "3":
            await check_all_priorities()
        elif choice == "4":
            print("프로그램을 종료합니다.")
            break
        else:
            print("잘못된 선택입니다.")
        
        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    asyncio.run(main())