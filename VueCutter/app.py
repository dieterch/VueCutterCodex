############################################################################################################
############################################################################################################
##                                                                                                        ##
## Quart VueCutter (c)2024 Dieter Chvatal backend                                                         ##
##                                                                                                        ##
############################################################################################################
############################################################################################################

import uvicorn
import asyncio
import json
import os
import signal
import sys
from pprint import pformat as pf
from pprint import pprint as pp
from quart import Quart, jsonify, render_template, request, redirect, url_for, send_file, abort
from quart_cors import cors
import subprocess
import time
from dplexapi.dplexdata import Plexdata
import wakeonlan

# overwrite jinja2 delimiters to avoid conflict with vue delimiters, was previosly used by me (Dieter Chvatal)
# in order to transfer information from the backend to the frontend, while the frontend does not know its host ip address.
# window.location.host and winndow.location.protocol is now used to get the host ip address. The code is left here for reference.
# https://stackoverflow.com/questions/37039835/how-to-change-jinja2-delimiters
class CustomQuart(Quart):
    jinja_options = Quart.jinja_options.copy()
    jinja_options.update(dict( block_start_string='<%', block_end_string='%>', variable_start_string='%%', 
                              variable_end_string='%%',comment_start_string='<#',comment_end_string='#>',))


# instantiate the app
# the frontend is built with vuetify.js and is located in the dist folder
# you have to set the static folder to the dist folder and the template folder to the dist folder in the backend like below
# and edit vite.config.js to output to the dist folder within the frontend. in adddition you have to
# run 'npm run build' after each modification of the frontend. Once you run this once, the included watch mode will
# take care of the rest.
app = CustomQuart(__name__, static_folder = "dist/static", template_folder = "dist", static_url_path = "/static")
app.config['PREFERRED_URL_SCHEME'] = 'https'
app = cors(app, allow_origin="*")
app.config.from_object(__name__)


# uncomment to disable caching, which is useful for development when you are actively changing the frontend
@app.after_request
async def add_header(response):
    """
    Add headers to both force latest IE rendering engine or Chrome Frame,
    and also to cache the rendered page for x minutes.
    """
    response.headers['X-UA-Compatible'] = 'IE=Edge,chrome=1'
    response.headers['Cache-Control'] = 'public, max-age=0'
    return response

# the functionality of the backend is provided by the Plexdata class, which is imported here
# the Plexdata class is a wrapper around the PlexAPI and the Cutter class
plexdata = Plexdata(os.path.dirname(__file__))


async def read_json_request():
    await request.get_data()
    body = await request.body
    return json.loads(body) if body else {}


def frame_url(filename, external=False):
    return url_for('static', filename=filename, _external=external)


def json_error(message, status=500):
    return jsonify({'error': message}), status

# routes to provide xspf files for VLC -> would be a candidate to be moved in a separate Quart blueprint
# all movies in plex
@app.route('/streamall.xspf')
async def streamsectionall():
        b = await plexdata.streamsectionall()
        return await send_file(b, as_attachment=True,
            attachment_filename='streamall.xspf',
            mimetype='text/xspf+xml')
        
# all movies in the section
@app.route('/streamsection.xspf')
async def streamsection():
        b = await plexdata.streamsection()
        return await send_file(b, as_attachment=True,
            attachment_filename='streamsection.xspf',
            mimetype='text/xspf+xml')
        
# the selected movie
@app.route('/streamurl.xspf')
async def streamurl():
        b = await plexdata.streamurl()
        return await send_file(b, as_attachment=True,
            attachment_filename='streamurl.xspf',
            mimetype='text/xspf+xml')
    
# the backend provides the following routes to the frontend
# routes to select a section, a serie, a season, a movie, to update a section, a serie, a season, a movie
@app.route("/selection")
async def selection():
    try:
        return plexdata.get_selection()
    except:
        abort(500)
    

@app.route("/update_section", methods=['POST'])
async def update_section():
        if request.method == 'POST':
            req = await read_json_request()
            await plexdata._update_section(req['section'])        
            print(f"update_section: {pf(req)}")
            return redirect(url_for('index'))    

@app.route("/force_update_section")
async def force_update_section():
        await plexdata._update_section(plexdata.section_title, force=True)        
        print(f"force_update_section.")
        return redirect(url_for('index'))

@app.route("/update_serie", methods=['POST'])
async def update_serie():
        if request.method == 'POST':
            req = await read_json_request()
            await plexdata._update_serie(req['serie'])        
            print(f"update_serie: {pf(req)}")
            return redirect(url_for('index'))

@app.route("/update_season", methods=['POST'])
async def update_season():
        if request.method == 'POST':
            req = await read_json_request()
            await plexdata._update_season(req['season'])        
            print(f"update_season: {pf(req)}")
            return redirect(url_for('index'))    

# route to get information about a movie
@app.route("/movie_info/", methods=['POST'])
async def set_movie_get_info():
        if request.method == 'POST':
            req = await read_json_request()
            try:
                return await plexdata._movie_info(req)
            except:
                return { 'error': 'error' }

# route to get specific information for the cutting process
@app.route("/movie_cut_info")
async def get_movie_cut_info():
        return await plexdata._movie_cut_info()    

# route to generate small pics for a timelind and deliver them to the frontend
@app.route("/timeline", methods=['POST'])
async def timeline():
        if request.method == 'POST':
            req = await read_json_request()
            r = await plexdata._timeline(req)
            return r     

# route to get a frame at a scpecific time position and deliver it to the frontend
@app.route("/frame/", methods=['POST'])
async def get_frame():
        if request.method == 'POST':
            req = await read_json_request()
            try:
                return { 'frame': frame_url(await plexdata._frame(req)) }
            except:
                return { 'frame': frame_url('error.png') }
                  

# route to get the actual post_time of the backend. This is used to update the frontend
@app.route("/pos")
async def get_pos():
        return { 'pos': plexdata._selection['pos_time'] }

# execute the cutting process. hand over the data to the rq worker
@app.route("/cut2", methods=['POST'])
async def do_cut2():
        if request.method == 'POST':
            req = await read_json_request()
            return await plexdata._cut2(req)            

# route to get the progress of the cutting process
@app.route("/progress")
async def progress():
        return await plexdata._doProgress()    


@app.route("/api/health")
async def api_health():
    return {
        'status': 'ok',
        'service': 'vuecutter-backend',
        'plex_alive': plexdata.hostalive(),
    }


@app.route("/api/selection")
async def api_selection():
    try:
        return plexdata.get_selection()
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/selection/section", methods=['POST'])
async def api_update_section():
    try:
        req = await read_json_request()
        await plexdata._update_section(req['section'])
        return plexdata.get_selection()
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/selection/reload", methods=['POST'])
async def api_reload_section():
    try:
        req = await read_json_request()
        section = req.get('section', plexdata.section_title)
        await plexdata._update_section(section, force=True)
        return plexdata.get_selection()
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/selection/series", methods=['POST'])
async def api_update_series():
    try:
        req = await read_json_request()
        await plexdata._update_serie(req['serie'])
        return plexdata.get_selection()
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/selection/season", methods=['POST'])
async def api_update_season():
    try:
        req = await read_json_request()
        await plexdata._update_season(req['season'])
        return plexdata.get_selection()
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/selection/movie", methods=['POST'])
async def api_update_movie():
    try:
        req = await read_json_request()
        section = req.get('section')
        serie = req.get('serie')
        season = req.get('season')
        if section:
            await plexdata._update_section(section)
        if serie:
            await plexdata._update_serie(serie)
        if season:
            await plexdata._update_season(season)
        await plexdata._update_movie(req.get('movie', ''))
        return plexdata.get_selection()
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/movie")
async def api_movie():
    try:
        selection = plexdata.get_selection()
        req = {
            'section': selection.get('section', ''),
            'movie': selection.get('movie', ''),
        }
        return await plexdata._movie_info(req)
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/movie-cut-info")
async def api_movie_cut_info():
    try:
        return await plexdata._movie_cut_info()
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/frame", methods=['POST'])
async def api_frame():
    try:
        req = await read_json_request()
        filename = await plexdata._frame(req)
        return {'frame': frame_url(filename, external=True)}
    except FileNotFoundError as exc:
        return json_error(str(exc), status=503)
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/timeline", methods=['POST'])
async def api_timeline():
    try:
        req = await read_json_request()
        result = await plexdata._timeline(req)
        return {'status': result}
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/cut", methods=['POST'])
async def api_cut():
    try:
        req = await read_json_request()
        return await plexdata._cut2(req)
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/analyze/recording", methods=['POST'])
async def api_analyze_recording():
    try:
        req = await read_json_request()
        return await plexdata._analyze_recording(req)
    except FileNotFoundError as exc:
        return json_error(str(exc), status=503)
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/analyze/recording/<job_id>")
async def api_analyze_recording_status(job_id):
    try:
        return await plexdata._analysis_status(job_id)
    except Exception as exc:
        return json_error(str(exc))


@app.route("/api/progress")
async def api_progress():
    try:
        return await plexdata._doProgress()
    except Exception as exc:
        return json_error(str(exc))

# exit the application
@app.route("/restart")
async def doexit():
    os.kill(os.getpid(), signal.SIGTERM)
    return redirect(url_for('index'))    

@app.route('/wakeonlan')
async def dowakeonlan():
    wakeonlan.send_magic_packet(plexdata.cfg['fileservermac'])
    return redirect(url_for('index'))

@app.route('/wolserver')
async def dowolserver():
    res = plexdata.wolserver()
    return redirect(url_for('index'))

# deliver the vuetify frontend
@app.route("/")
async def index():
    return {
        'service': 'vuecutter-backend',
        'status': 'ok',
        'ui_url': os.getenv('VUECUTTER_UI_URL', 'http://localhost:8200'),
        'api': {
            'selection': '/api/selection',
            'movie': '/api/movie',
            'frame': '/api/frame',
            'timeline': '/api/timeline',
            'cut': '/api/cut',
            'analyze_recording': '/api/analyze/recording',
            'progress': '/api/progress',
        },
    }

if __name__ == '__main__':
    print('''
\033[H\033[J
****************************************************
* Vue Quart WebCutter V0.01 (c)2024 Dieter Chvatal *
* Async Backend                                    *
****************************************************
''')
    try:
        if 'PRODUCTION' in os.environ:
            uvicorn.run(
                 'app:app', 
                 host='0.0.0.0', 
                 port=5200, 
                 log_level="info",
                 proxy_headers=True,
                 forwarded_allow_ips="*",
                 #ssl_keyfile="/etc/certs/dvuecutter.home.smallfamilybusiness.net-key.pem",
                 #ssl_certfile="/etc/certs/dvuecutter.home.smallfamilybusiness.net.pem"
                 )
        else:
            uvicorn.run(
                 'app:app', 
                 host='0.0.0.0', 
                 port=5200, 
                 log_level="info",
                 proxy_headers=True,
                 forwarded_allow_ips="*",
                 reload=True, 
                 reload_dirs =['.','./dist'], 
                 reload_includes=['*.py','*.js'],
                 #ssl_keyfile="/etc/certs/dvuecutter.home.smallfamilybusiness.net.crt",
                 #ssl_certfile="/etc/certs/dvuecutter.home.smallfamilybusiness.net.key"
                 )
            #asyncio.run(app.run_task(host='0.0.0.0', port=5200, debug=True))
    except Exception as e:
        print(f"main: {str(e)}")
    finally:
        try:
            plexdata.cutter.umount()
        except Exception:
            pass
        print('Bye!')
