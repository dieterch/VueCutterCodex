# fresh compile at startup
pushd ./vue-cutter
npm install
npm run justbuild
popd
export PRODUCTION="1"
python -OO worker.py & 
python -OO app.py
