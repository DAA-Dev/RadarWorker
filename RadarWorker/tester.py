import logging, config
from workers import MapWorker
from datetime import datetime, timezone
from RadarWorker import RadarWorker

TAG = 'tester - '
LOC_FOLS = config.LOC_FOLS

logging.info(TAG+'beginning test')
config.init_environment()

test_time = datetime(2016, 3, 23, 12, 31, 30, tzinfo=timezone.utc)
worker = RadarWorker(test_time)
worker.pull_data()
print(worker)

print()

logging.info(TAG+'beginning to test the MapWorker')

map_worker = MapWorker.MapWorker([42.114229, -88.113506])
map_worker.gps_coordinate = [42.114229, -88.113506]
#map_worker = mapworker.MapWorker([39.547561, -104.980642])


