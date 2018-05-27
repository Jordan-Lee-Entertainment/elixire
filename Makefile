all: frontend panel

.PHONY: all frontend panel

frontend:
	echo "Building frontend"
	cd frontend; npm i
	cd frontend; npm run build:production

panel:
	echo "Building Admin Panel"
	cd admin-panel; npm i
	cd admin-panel; npm run build
