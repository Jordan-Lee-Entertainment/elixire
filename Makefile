all: frontend admin-panel

.PHONY: all frontend admin-panel

# we can use docker to build frontend as it doesn't build on latest node
# at the moment. useful for development
frontend:
	echo "Building frontend"
ifeq ($(DOCKER),1)
	docker run --mount type=bind,source=$(shell pwd)/frontend,target=/frontend -it \
	    --rm mhart/alpine-node:10 sh -c "cd frontend && yarn install && yarn build:production"
else
	cd frontend; yarn
	cd frontend; yarn build:production
endif

admin-panel:
	echo "Building admin-panel"
	cd admin-panel; npm ci
	cd admin-panel; npm run build

update:
	echo "Pulling and updating submodules"
	git pull
	git submodule foreach git pull origin master

clean:
	cd frontend; rm -rf node_modules
	cd admin-panel; rm -rf node_modules

get-legal:
	git submodule add -f https://gitlab.com/elixire/legal.git

link-legal:
	PWD=$(pwd)
	ln ${PWD}/legal/privacy_policy.pug ${PWD}/frontend/src/privacy.pug
