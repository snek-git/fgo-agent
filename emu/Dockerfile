# redroid 13 + Google's libndk ARM translation (ChromeOS zork R136 build), root signals removed.
# The older 0.2.3 libndk (Android 11) dies on Unity 6's SEVL instruction, so this needs the newer one.
FROM alpine:3 AS ndk
ARG NDK_COMMIT=68734c52556d3d7a6db34c603dd9276915c29f2f
RUN apk add --no-cache curl unzip \
 && curl -fsSL -o /ndk.zip \
      "https://github.com/supremegamers/vendor_google_proprietary_ndk_translation-prebuilt/archive/${NDK_COMMIT}.zip" \
 && unzip -q /ndk.zip -d /src \
 && mkdir -p /out \
 && cp -r /src/*/prebuilts /out/system \
 && chmod -R a+rX /out/system \
 && chmod 0644 /out/system/etc/init/ndk_translation.rc \
 && chmod 0755 /out/system/bin/ndk_translation_program_runner_binfmt_misc*

FROM redroid/redroid:13.0.0-latest AS base

# Android binaries can't run during docker build (bionic lives in an apex mounted at boot),
# so the rootfs is edited from an alpine stage and copied back.
FROM alpine:3 AS mod
COPY --from=base / /rootfs/
COPY --from=ndk /out/ /rootfs/
RUN rm -f /rootfs/system/xbin/su \
 && for f in /rootfs/system/build.prop /rootfs/vendor/build.prop /rootfs/product/etc/build.prop \
             /rootfs/system_ext/etc/build.prop /rootfs/odm/etc/build.prop; do \
      if [ -f "$f" ]; then sed -i -e 's/test-keys/release-keys/g' -e 's/userdebug/user/g' "$f"; fi; \
    done

FROM scratch
COPY --from=mod /rootfs/ /
ENTRYPOINT ["/init", "qemu=1", "androidboot.hardware=redroid"]
