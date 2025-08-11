import asyncio
from bacpypes3.local.device import DeviceObject
from bacpypes3.pdu import Address, IPv4Address
from bacpypes3.primitivedata import ObjectIdentifier, Null
from bacpypes3.apdu import WritePropertyRequest
from bacpypes3.ipv4.app import NormalApplication
from bacpypes3.constructeddata import Any

async def write_priority_null(app, target_ip, obj_type, obj_inst, prop_id, priority_slot):
    # Null 값을 Any로 래핑
    bacnet_value = Any(Null())

    request = WritePropertyRequest(
        objectIdentifier=ObjectIdentifier((obj_type, obj_inst)),
        propertyIdentifier=prop_id,
        propertyValue=bacnet_value,
        priority=priority_slot
    )
    request.pduDestination = Address(target_ip)

    response = await app.request(request)
    if response:
        print(f"Priority {priority_slot} null write succeeded on {obj_type} {obj_inst} {prop_id}")
    else:
        print("Write failed or no response")

async def main():
    device = DeviceObject(
        objectName="LocalDevice",
        objectIdentifier=("device", 1234),
        maxApduLengthAccepted=1024,
        segmentationSupported="segmentedBoth",
        vendorIdentifier=999
    )
    local_address = IPv4Address("200.0.0.234/24")
    app = NormalApplication(device, local_address)

    await write_priority_null(
        app,
        target_ip="200.0.0.162",
        obj_type="analogOutput",
        obj_inst=1,
        prop_id="presentValue",
        priority_slot=2
    )

if __name__ == "__main__":
    asyncio.run(main())
