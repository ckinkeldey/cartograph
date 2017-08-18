import re
import falcon
import logging
import os
import sys
from falcon_multipart.middleware import MultipartMiddleware

from cartograph.server import ServerConfig
from cartograph.server.ParentService import ParentService, METACONF_FLAG
from cartograph.server.AddMapService2 import AddMapService
from cartograph.server.Map import Map
from cartograph.server.StaticService import StaticService
from cartograph.server.UploadService import UploadService


logging.basicConfig(stream=sys.stderr, level=logging.INFO)

# Initialize the server configuration
if __name__ == '__main__' and len(sys.argv) > 1:
    server_config_path = sys.argv[1]
elif os.getenv('CARTOGRAPH_SERVER_CONFIG'):
    server_config_path = os.getenv('CARTOGRAPH_SERVER_CONFIG')
else:
    server_config_path = './conf/default_server.conf'
logging.info('using server config: ' + repr(server_config_path))
server_config = ServerConfig.init(server_config_path)

# Initialize the meta map configuration
# TODO: SWS: Make meta the only available config
if __name__ == '__main__' and len(sys.argv) > 2:
    meta_config_path = sys.argv[2]
elif os.getenv('CARTOGRAPH_CONFIGS'):
    meta_config_path = os.getenv('CARTOGRAPH_CONFIGS')
else:
    meta_config_path = server_config.get('DEFAULT', 'default_multi_map_config')
logging.info('using meta map config: ' + repr(meta_config_path))
if not os.path.isfile(meta_config_path):
    logging.info('meta map config doesnt exist, so creating an empty one.')
    with open(meta_config_path, 'w') as f:
        f.write(METACONF_FLAG + '\n')
server_config = ServerConfig.init(server_config_path)

configs = {}

logging.info('configuring falcon')


# falcon.API instances are callable WSGI apps
app = falcon.API(middleware=[MultipartMiddleware()])

# Determine whether the input file is a multi-config (i.e. paths to multiple files) or a single config file
with open(meta_config_path, 'r') as meta_config:
    first_line = meta_config.readline().strip('\r\n')
    if first_line != METACONF_FLAG:
        conf_files = [meta_config_path]
        map_services = {'_multi_map': False}
    else:
        conf_files = re.split('[\\r\\n]+', meta_config.read())  # Note that the .readline() above means we skip the first line
        map_services = {'_multi_map': True}


# Start up a set of services (i.e. a MapService) for each map (as specified by its config file)
for path in conf_files:
    if path == '':
        continue  # Skip blank lines
    map_service = Map(path)
    map_services[map_service.name] = map_service
map_services['_meta_config'] = meta_config_path
map_services['_last_update'] = os.path.getmtime(meta_config_path)


# Start a ParentService for each service; a ParentService represents a given service for every map in <map_services>
app.add_route('/{map_name}/search.json', ParentService(map_services, 'search_service'))
app.add_route('/{map_name}/vector/{layer}/{z}/{x}/{y}.topojson', ParentService(map_services, 'tile_service'))
app.add_route('/{map_name}/raster/{layer}/{z}/{x}/{y}.png', ParentService(map_services, 'mapnik_service'))
app.add_route('/{map_name}/template/{file}', ParentService(map_services, 'template_service'))
app.add_route('/{map_name}/point.json', ParentService(map_services, 'related_points_service'))
app.add_route('/{map_name}/log', ParentService(map_services, 'logging_service'))
app.add_route('/{map_name}/add_metric/{metric_type}', ParentService(map_services, 'add_metric_service'))
app.add_route('/{map_name}/info', ParentService(map_services, 'info_service'))
app.add_sink(ParentService(map_services, 'static_service').on_get, '/(?P<map_name>.+)/static')


# If the server is in multi-map mode, provide hooks for adding new maps
if map_services['_multi_map']:
    UPLOAD_DIR = 'tmp/upload'
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    app.add_route('/upload', UploadService(server_config, map_services))
    app.add_route('/add_map', AddMapService(server_config, map_services))


# Add way to get static files generally (i.e. without knowing the name of any active map)
app.add_sink(StaticService().on_get, '/static')


# Useful for debugging problems in your API; works with pdb.set_trace(). You
# can also use Gunicorn to host your app. Gunicorn can be configured to
# auto-restart workers when it detects a code change, and it also works
# with pdb.
if __name__ == '__main__':
    logging.info('starting server')

    from wsgiref import simple_server
    httpd = simple_server.make_server(server_config.get('DEFAULT', 'host'),
                                      int(server_config.get('DEFAULT', 'port')),
                                      app)
    logging.info('server ready!')
    httpd.serve_forever()