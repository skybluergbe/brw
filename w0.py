import BAC0
import asyncio

async def write_null_to_priority_async(ip, obj_type, obj_inst, priority):
    try:
        async with BAC0.connect(ip) as bacnet:
            object_string = f"{obj_type} {obj_inst} at {ip}"
            
            print(f"✅ BACnet 통신 시작: {"200.0.0.234"}")
            print(f"▶️ {object_string}의 우선순위 {priority}에 null 값 쓰기 요청...")

            # await를 사용하여 비동기 write() 메서드가 완료될 때까지 기다립니다.
            # 'None'을 전달하여 null 값을 입력합니다.
            result = await bacnet.write(object_string, None, priority=priority)

            print("---")
            print(f"✅ 요청 성공: {object_string}의 우선순위 {priority}가 해제되었습니다.")
            print(f"✅ 응답: {result}")
            print("---")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

async def main():
    DEVICE_IP = "200.0.0.162"
    OBJECT_TYPE = "analogValue"
    OBJECT_INSTANCE = 1
    TARGET_PRIORITY = 8

    await write_null_to_priority_async(DEVICE_IP, OBJECT_TYPE, OBJECT_INSTANCE, TARGET_PRIORITY)

if __name__ == "__main__":
    asyncio.run(main())