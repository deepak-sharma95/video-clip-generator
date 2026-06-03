import time, requests, json
print('Starting extraction via API with new settings: 30s duration, 2 clips, 9:16 format...')
res = requests.post('http://localhost:5000/api/extract', json={'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'duration': 30, 'clips': 2, 'format': '9:16'})
job_id = res.json()['job_id']
print(f'Job ID: {job_id}')

while True:
    status = requests.get(f'http://localhost:5000/api/status/{job_id}').json()
    print(f"Status: {status['status']} - {status['progress']}")
    if status['status'] == 'completed':
        print('Results:')
        print(json.dumps(status['results'], indent=2))
        break
    elif status['status'] == 'error':
        print(f"Error: {status['error']}")
        break
    time.sleep(3)
