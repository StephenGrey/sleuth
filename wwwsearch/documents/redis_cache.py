# -*- coding: utf-8 -*-
import redis

redis_connection=redis.Redis(charset="utf-8", decode_responses=True)


def delete_job(job):
    return redis_connection.delete(job)
    
