#!/usr/bin/env python3

import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, TagList, Tag, TagClass, TagNumber
from bacpypes3.apdu import WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication

async def write_null_to_priority(target_device, object_id, priority=1):
    """우선순위에 NULL 값 쓰기 - 수동 태그 생성"""
    try:
        # BACnet 디바이스 설정
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
        
        print("=" * 50)
        print("BACnet NULL 쓰기")
        print("=" * 50)
        print(f"타겟 디바이스: {target_device}")
        print(f"객체: {object_id}")
        print(f"우선순위: {priority}")
        print()
        
        # NULL 태그 수동 생성
        # BACnet NULL은 태그 번호 0, 길이 0
        null_tag = Tag(
            tag_class=TagClass.application,
            tag_number=TagNumber(0),  # NULL의 태그 번호
            tag_data=b''  # 빈 데이터
        )
        
        # TagList에 NULL 태그 추가
        tag_list = TagList()
        tag_list.append(null_tag)
        
        # 쓰기 요청 생성
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier="presentValue",
            propertyValue=tag_list  # TagList 직접 사용
        )
        
        # 우선순위 설정
        request.priority = priority
        request.pduDestination = Address(target_device)
        
        print(f"우선순위 {priority}에 NULL 전송 중...")
        
        # 요청 전송
        response = await app.request(request)
        
        if response:
            print("✅ NULL 전송 성공!")
            return True
        else:
            print("❌ 전송 실패: 응답 없음")
            return False
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def write_null_simple(target_device, object_id, priority=1):
    """더 간단한 NULL 쓰기 시도"""
    try:
        # BACnet 디바이스 설정
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
        
        print("=" * 50)
        print("BACnet NULL 쓰기 (간단한 방법)")
        print("=" * 50)
        print(f"타겟 디바이스: {target_device}")
        print(f"객체: {object_id}")
        print(f"우선순위: {priority}")
        print()
        
        # priorityArray에 직접 쓰기
        request = WritePropertyRequest(
            objectIdentifier=ObjectIdentifier(object_id),
            propertyIdentifier="priorityArray",
            propertyArrayIndex=priority
        )
        
        # NULL 태그 생성
        null_tag = Tag(
            tag_class=TagClass.application,
            tag_number=TagNumber(0),
            tag_data=b''
        )
        
        tag_list = TagList()
        tag_list.append(null_tag)
        
        request.propertyValue = tag_list
        request.pduDestination = Address(target_device)
        
        print(f"priorityArray[{priority}]에 NULL 전송 중...")
        
        # 요청 전송
        response = await app.request(request)
        
        if response:
            print("✅ NULL 전송 성공!")
            return True
        else:
            print("❌ 전송 실패: 응답 없음")
            return False
            
    except Exception as e:
        print(f"❌ 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """메인 함수"""
    # 설정값
    target_device = "200.0.0.162"
    object_id = ("analogOutput", 1)
    priority = 2
    
    print("방법 1: presentValue에 NULL 쓰기")
    success = await write_null_to_priority(target_device, object_id, priority)
    
    if not success:
        print("\n방법 2: priorityArray에 직접 NULL 쓰기")
        success = await write_null_simple(target_device, object_id, priority)
    
    if success:
        print("\n🎉 우선순위 NULL 설정 완료!")
    else:
        print("\n😞 우선순위 NULL 설정 실패")
        print("\n대안: 우선순위 16을 시도하거나 장치 웹 인터페이스를 사용하세요.")

if __name__ == "__main__":
    asyncio.run(main())