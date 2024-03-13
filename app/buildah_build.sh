# Warning: This was not working on Buldah 1.22, it works perfectly fine on 1.28
# Set your manifest name
export MANIFEST_NAME="cilium-secondary-interface-route-manager"
# Set the required variables
export REGISTRY="quay.io"
export USER="datacenter"
export IMAGE_NAME="cilium-secondary-interface-route-manager"
export IMAGE_TAG="v0.0.2"


# Clean up and Create a multi-architecture manifest
for i in `buildah manifest inspect ${MANIFEST_NAME} | jq -r ".manifests[].digest"`
    do
    buildah manifest remove ${MANIFEST_NAME}  $i
    done
buildah manifest rm ${MANIFEST_NAME} 
buildah manifest create ${MANIFEST_NAME}

### MAIN CONTAINER
# Build your amd64 architecture container
buildah bud \
    --tag "${REGISTRY}/${USER}/${IMAGE_NAME}:${IMAGE_TAG}" \
    --manifest ${MANIFEST_NAME} \
    --arch=amd64 \
    --layers &
    
# Build your arm64 architecture container
buildah bud \
    --tag "${REGISTRY}/${USER}/${IMAGE_NAME}:${IMAGE_TAG}" \
    --manifest ${MANIFEST_NAME} \
    --arch arm64 \
    --layers &

wait # Wait for all the builds to finish

# Push the full manifest, with both CPU Architectures
buildah manifest push --all \
    ${MANIFEST_NAME} \
    "docker://${REGISTRY}/${USER}/${IMAGE_NAME}:${IMAGE_TAG}"