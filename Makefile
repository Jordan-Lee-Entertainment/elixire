all: frontend panel

.PHONY: all frontend panel

frontend:
	echo "Building frontend"
	cd frontend; yarn
	cd frontend; yarn build:production

panel:
	echo "Building Admin Panel"
	cd admin-panel; yarn
	cd admin-panel; yarn build

update:
	echo "Pulling and updating submodules"
	git pull
	git submodule foreach git pull
