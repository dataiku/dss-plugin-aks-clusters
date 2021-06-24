PLUGIN_VERSION=2.0.0
PLUGIN_ID=aks-clusters

plugin:
	cat plugin.json|json_pp > /dev/null
	rm -rf dist
	mkdir dist
	zip --exclude "*.pyc" -r dist/dss-plugin-${PLUGIN_ID}-${PLUGIN_VERSION}.zip plugin.json code-env parameter-sets python-clusters python-lib python-runnables
