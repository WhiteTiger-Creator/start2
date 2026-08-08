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

# /app/data/jobs.json ships holding the stale partial instance the failed
# rollout left behind. The released routings, the routing template library and
# the shop calendar beside it are the sources the expansion has to be rebuilt
# from before the scheduler reads that path. All values are synthetic.
COPY app/ /app/
RUN cp /app/workflow/scheduler.py /app/workflow/.scheduler.original \
    && chmod a-w /app/workflow/.scheduler.original
