# redroid 11 + libndk (built by vendor/redroid-script -n), with the usual root signals removed.
# Android binaries can't run during docker build (bionic lives in an apex mounted at boot),
# so the rootfs is edited from an alpine stage and copied back.
FROM redroid/redroid:11.0.0_ndk AS base

FROM alpine:3 AS mod
COPY --from=base / /rootfs/
RUN rm -f /rootfs/system/xbin/su \
 && for f in /rootfs/system/build.prop /rootfs/vendor/build.prop /rootfs/product/etc/build.prop \
             /rootfs/system_ext/etc/build.prop /rootfs/odm/etc/build.prop; do \
      if [ -f "$f" ]; then sed -i -e 's/test-keys/release-keys/g' -e 's/userdebug/user/g' "$f"; fi; \
    done

FROM scratch
COPY --from=mod /rootfs/ /
ENTRYPOINT ["/init", "qemu=1", "androidboot.hardware=redroid"]
