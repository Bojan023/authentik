"""Kubernetes Service Reconciler"""
from typing import TYPE_CHECKING

from kubernetes.client import CoreV1Api, V1Service, V1ServicePort, V1ServiceSpec

from authentik.outposts.controllers.base import FIELD_MANAGER
from authentik.outposts.controllers.k8s.base import KubernetesObjectReconciler, NeedsRecreate
from authentik.outposts.controllers.k8s.deployment import DeploymentReconciler

if TYPE_CHECKING:
    from authentik.outposts.controllers.kubernetes import KubernetesController


class ServiceReconciler(KubernetesObjectReconciler[V1Service]):
    """Kubernetes Service Reconciler"""

    def __init__(self, controller: "KubernetesController") -> None:
        super().__init__(controller)
        self.api = CoreV1Api(controller.client)

    def reconcile(self, current: V1Service, reference: V1Service):
        if len(current.spec.ports) != len(reference.spec.ports):
            raise NeedsRecreate()
        for port in reference.spec.ports:
            if port not in current.spec.ports:
                raise NeedsRecreate()
        # run the base reconcile last, as that will probably raise NeedsUpdate
        # after an authentik update. However the ports might have also changed during
        # the update, so this causes the service to be re-created with higher
        # priority than being updated.
        super().reconcile(current, reference)

    def get_reference_object(self) -> V1Service:
        """Get deployment object for outpost"""
        meta = self.get_object_meta(name=self.name)
        ports = []
        for port in self.controller.deployment_ports:
            ports.append(
                V1ServicePort(
                    name=port.name,
                    port=port.port,
                    protocol=port.protocol.upper(),
                    target_port=port.inner_port or port.port,
                )
            )
        if self.is_embedded:
            selector_labels = {
                "app.kubernetes.io/name": "authentik",
                "app.kubernetes.io/component": "server",
            }
        else:
            selector_labels = DeploymentReconciler(self.controller).get_pod_meta()
        return V1Service(
            metadata=meta,
            spec=V1ServiceSpec(
                ports=ports,
                selector=selector_labels,
                type=self.controller.outpost.config.kubernetes_service_type,
            ),
        )

    def create(self, reference: V1Service):
        return self.api.create_namespaced_service(
            self.namespace, reference, field_manager=FIELD_MANAGER
        )

    def delete(self, reference: V1Service):
        return self.api.delete_namespaced_service(reference.metadata.name, self.namespace)

    def retrieve(self) -> V1Service:
        return self.api.read_namespaced_service(self.name, self.namespace)

    def update(self, current: V1Service, reference: V1Service):
        return self.api.patch_namespaced_service(
            current.metadata.name,
            self.namespace,
            reference,
            field_manager=FIELD_MANAGER,
        )
