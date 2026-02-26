"""
간단한 Docker 배포 테스트
"""
import yaml

# 매우 간단한 compose 파일 생성
compose = {
    'version': '3.8',
    'services': {
        'test_ubuntu': {
            'image': 'ubuntu:22.04',
            'container_name': 'test_agent_ubuntu',
            'command': 'sleep infinity',
            'networks': ['test_network']
        }
    },
    'networks': {
        'test_network': {
            'driver': 'bridge'
        }
    }
}

with open('test_compose.yml', 'w') as f:
    yaml.dump(compose, f)

print("✅ test_compose.yml 생성 완료")
print("\n테스트 방법:")
print("1. docker-compose -f test_compose.yml up -d")
print("2. docker ps | grep test_agent")
print("3. docker-compose -f test_compose.yml down")
