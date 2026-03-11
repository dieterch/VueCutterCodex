Quart VueCutter
========
\(c\) 2024 Dieter Chvatal

- This is a fullstack web-application with a backend in Python using the Quart framework, the backend is responsible for providing the frontend with the necessary data and for executing the cutting process. The cutting process is executed by an rq worker, which is started as a seperate process 'python worker.py'.  
- ffmpeg is required for picture extraction and movie cut.  
- The rq queue requires a redis server. In my case, the redis server is provided by a docker container (specified by a docker-compose.yml file).
- The frontend consists of a vuetify-vue SPA located in the subfolder vue-cutter. The compiled application is delivered by the Quart ASGI Webserver, so rest Interface and frontend share one 'ip:port'.
- A Plex Server in the local network is obviously required. python PlexAPI package is used to access the Plex Server. 

Installation
------------
To configure this application, you have to create a **config.toml** file in the same directory as this file with the following content:
:: 
  fileserver = 'xx.xx.xx.xx'
  plexurl = 'http://xx.xx.xx.xx:32400'
  plextoken = 'xxxxxxxxxxxxxxxxxx'
  redispw = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
::

Software:
:: 
  1.create a folder on a raspberry pi 4+ or similar device: git clone https://github.com/dieterch/VueCutter.git
  2.install the python part in a virtual envirinment with the following commands:
    a) python -m venv venv
    b) source venv/bin/activate
    c) pip install -r requirements.txt
  3.Install the frontend with the following commands:
    a) cd vue-cutter
    b) npm install
    c) npm run build
::

Create a redis server with the following docker-compose.yml:
::
 version: '3.8'
 services:
   server:
     image: redis:6.2-alpine
     restart: always
     ports:
       - '6379:6379'                                                       
     command: redis-server --save 20 1 --loglevel warning --requirepass xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
     volumes:
       - server:/data
 volumes:
   server:
     driver: local
::

Start
------
- start and fetch the redis server from docker with 'docker-compose up'
- install tmux
- copy _VueCutter to your home directory
- . _VueCutter
- manually leave tmux with **ctrl+b and d** (processes now in background)
- attach to tmux with **tmux attach**
- stop each process with ctrl+c with tmux attached

Release History
---------------

- 0.0.1 initial release as Quartcutter
- 0.1.0 frontend updated to vue 3 / Vuetify 3
- Work in progress

Meta
----

My Name – dieter.chvatal@gmail.com

Distributed under the MIT license. See ``LICENSE`` for more information.

`https://github.com/dieterch/vuecutter <https://github.com/dieterch/>`__


Contributing
------------

1. Fork it (https://github.com/dieterch/vuecutter)
2. Create your feature branch (``git checkout -b feature/fooBar``)
3. Commit your changes (``git commit -am 'Add some fooBar'``)
4. Push to the branch (``git push origin feature/fooBar``)
5. Create a new Pull Request
