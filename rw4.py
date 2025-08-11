#!/usr/bin/env python3
import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Real, Null
from bacpypes3.apdu import ReadPropertyRequest, WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.constructeddata import Any

_debug = 0

def extract_value(bacnet_value):
    if bacnet_value is None:
        return None
    try:
        from bacpypes3.primitivedata import Real, CharacterString
        real_val = bacnet_value.cast_out(Real)
        if real_val is not None:
            return float(real_val)
        str_val = bacnet_value.cast_out(CharacterString)
        if str_val is not None:
            return str(str_val)
        return str(bacnet_value)
    except Exception:
        return f"값 추출 실패: {bacnet_value}"

async def read_property(app, target_device, object_id, property_id):
    req = ReadPropertyRequest(objectIdentifier=ObjectIdentifier(object_id),
                              propertyIdentifier=property_id)
    req.pduDestination = Address(target_device)
    resp = await app.request(req)
    if resp:
        return extract_value(resp.propertyValue)
    return None

async def write_single_value(app, target_device, object_id, property_id, value, priority=16):
    print(f"\n쓰기 대상: {target_device}, 객체: {object_id}, 속성: {property_id}, 값: {value}, 우선순위: {priority}")

    obj_name = await read_property(app, target_device, object_id, "objectName")
    print("객체 이름:", obj_name or "읽을 수 없음")

    current = await read_property(app, target_device, object_id, property_id)
    print("현재 값:", current if current is not None else "읽을 수 없음")

    if value is None:
        bacnet_value = Any(Null())
    else:
        bacnet_value = Any(Real(value))

    req = WritePropertyRequest(
        objectIdentifier=ObjectIdentifier(object_id),
        propertyIdentifier=property_id,
        propertyValue=bacnet_value
    )
    req.priority = priority
    req.pduDestination = Address(target_device)

    resp = await app.request(req)
    if resp:
        print("쓰기 성공")
        await asyncio.sleep(0.5)
        new = await read_property(app, target_device, object_id, property_id)
        print("확인된 값:", new)
    else:
        print("응답 없음, 실패")

async def main():
    # 앱과 로컬 장치 초기화 (한 번만)
    device = DeviceObject(
        objectName="BACnetWriter",
        objectIdentifier=("device", 599),
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=15
    )
    local_address = IPv4Address("0.0.0.234/24")
    app = NormalApplication(device, local_address)

    target = "200.0.0.162"
    obj_id = ("analogOutput", 1)
    prop = "presentValue"

    #await write_single_value(app, target, obj_id, prop, 43, priority=2)
    await write_single_value(app, target, obj_id, prop, None, priority=2)

if __name__ == "__main__":
    asyncio.run(main())
