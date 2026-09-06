# Pin BASE_IMAGE to its resolved digest before validation.
ARG BASE_IMAGE=ubuntu@sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517
FROM ${BASE_IMAGE}
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends python3 nodejs acl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN groupadd -g 22000 hermes-policy-read \
    && for pair in scout:21001 analyst:21002 strategist:21003 guardian:21004 executor:21005 observer:21006 orchestrator:21007; do \
         role=${pair%:*}; uid=${pair#*:}; \
         groupadd -g "$uid" "hermes-$role"; \
         useradd -u "$uid" -g "$uid" -G hermes-policy-read -m -s /usr/sbin/nologin "hermes-$role"; \
         chmod 0700 "/home/hermes-$role"; \
       done
COPY linux_validation.py /validation/linux_validation.py
ENTRYPOINT ["python3", "/validation/linux_validation.py"]
