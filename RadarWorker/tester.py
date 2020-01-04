import logging, config
from workers import MapWorker
from datetime import datetime, timezone
from RadarWorker import RadarWorker

TAG = 'tester - '
LOC_FOLS = config.LOC_FOLS

logging.info(TAG+'beginning test')
config.init_environment()

test_time = datetime(2020, 1, 3, 2, 0, 30, tzinfo=timezone.utc)
worker = RadarWorker(test_time)
worker.pull_data()
worker.gps_to_pixel([38.433104, -101.844919])

print(worker)

print()

logging.info(TAG+'beginning to test the MapWorker')

map_worker = MapWorker.MapWorker([44.971666, -70.919625])
bp = map_worker.get_bounding_points()
worker.create_overlay_image(map_worker)


#map_worker.gps_coordinate = [39.234055, -118.387577]
#bp = map_worker.get_bounding_points()
#worker.create_overlay_image(bp[0], bp[1], map_worker.tilepath)

#map_worker.gps_coordinate = [42.114229, -88.113506])
#map_worker = mapworker.MapWorker([39.547561, -104.980642])

# NEXT ON AGENDA:
# Fix program to work at any zoom level

