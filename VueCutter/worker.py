import time
import os
from redis import Redis
from redis.exceptions import ConnectionError
from rq import Connection, Queue, Worker
import tomllib

from dplexapi.dcut import CutterInterface

config_path = os.getenv('PLEXDATA_CONFIG', 'config.toml')
with open(config_path, mode="rb") as fp:
    cfg = tomllib.load(fp)

fileserver = os.getenv('VUECUTTER_FILESERVER', cfg['fileserver'])
cutter = CutterInterface(fileserver)

redis_host = os.getenv('REDIS_HOST', 'redis' if os.getenv('IN_DOCKER') == 'true' else 'localhost')
redis_port = int(os.getenv('REDIS_PORT', '6379'))
redis_password = os.getenv('REDIS_PASSWORD', os.getenv('VUECUTTER_REDIS_PASSWORD', cfg.get('redispw', '')))
redis_kwargs = {
    'host': redis_host,
    'port': redis_port,
}
if redis_password:
    redis_kwargs['password'] = redis_password

print(f"Worker connecting to redis at {redis_host}:{redis_port}")
redis_connection = Redis(**redis_kwargs)

if __name__ == '__main__':
    for i in range(10):
        try:
            with Connection(redis_connection):
                print(f"Worker connecting to redis ...")
                worker = Worker(Queue('VueCutter'))
                worker.work()
                break
        except (ConnectionError, ConnectionRefusedError) as err:
        #except Exception as err:
            print(str(err), f"... retry {i+1}/10 ...")
            time.sleep(5)
    print(f"giving up ... QuartCutter Worker Execution ended.")

#redis.exceptions.ConnectionError
