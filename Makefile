all: frontend panel

.PHONY: all frontend panel

frontend:
	echo "Building frontend"
	cd frontend; yarn
	cd frontend; yarn build:production

panel:
	echo "Building Admin Panel"
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
