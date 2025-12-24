SHELL := /bin/bash

.PHONY: all prereqs bootstrap infra images kube csi deploy validate destroy

all: prereqs bootstrap infra images kube csi deploy validate

prereqs:
	./scripts/00_prereqs_check.sh

bootstrap:
	./scripts/01_bootstrap_login.sh

infra:
	./scripts/02_provision_infra.sh

images:
	./scripts/03_build_and_push_images.sh

kube:
	./scripts/04_connect_kubectl.sh

csi:
	./scripts/05_install_csi_workload_identity.sh

deploy:
	./scripts/06_deploy_apps.sh

validate:
	./scripts/07_validate.sh

destroy:
	./scripts/99_destroy.sh
