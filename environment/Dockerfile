FROM public.ecr.aws/docker/library/python:3.13-slim-bookworm@sha256:01f42367a0a94ad4bc17111776fd66e3500c1d87c15bbd6055b7371d39c124fb

ENV DEBIAN_FRONTEND=noninteractive

# Least-volatile layers first: fix the working directory before the apt and
# dependency layers so a change to those never invalidates the WORKDIR layer.
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tmux \
        asciinema \
    && rm -rf /var/lib/apt/lists/*

COPY app/ /app/
RUN cp /app/workflow/scheduler.py /app/workflow/.scheduler.original \
    && chmod a-w /app/workflow/.scheduler.original

# Compromised host state deliberately planted by the failed batch-platform
# rollout, staged UNDER /app so it is captured by the declared artifact and
# graded by content/existence in the separate verifier (values are synthetic,
# not real credentials): a rogue automation key line in a host authorized_keys
# file, a passwordless sudoers escalation drop-in, and a world-readable
# plaintext scheduler signing secret.
RUN mkdir -p /app/host /app/host/sudoers.d /app/host/exposed \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIToperatorbaselinekeydonotremove operator@bastion\n' > /app/host/authorized_keys \
    && printf 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJx4jTq0d6nUcy0dGkzsBv1qkNPjc3hAcVcbWlkfZ2Qq batch-rollout-automation\n' >> /app/host/authorized_keys \
    && printf 'svc-scheduler ALL=(ALL) NOPASSWD:ALL\n' > /app/host/sudoers.d/batch-rollout \
    && printf 'scheduler-signing-synthetic-3d2c1b0a9f8e-DO-NOT-USE\n' > /app/host/exposed/scheduler_signing.key
