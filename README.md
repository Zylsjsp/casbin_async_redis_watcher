# casbin_async_redis_watcher
async casbin redis watcher

# async-redis-watcher

async-redis-watcher is the [Redis](https://github.com/redis/redis) watcher for [pycasbin](https://github.com/casbin/pycasbin). With this library, Casbin can synchronize the policy with the database in multiple enforcer instances.


# what is redis-watcher's problem? 

When use web framework like FastApi, the event loop run in main thread, but redis-watcher start a new Thread for monitor policy change and synchronize the policy .

So when use sqlalchemy as AsyncEnforcer,  because there has two loop in diff thread

```python
def new_watcher(option: WatcherOptions):
    option.init_config()
    w = RedisWatcher()
    rds = Redis(host=option.host, port=option.port, password=option.password, ssl=option.ssl)
    if rds.ping() is False:
        raise Exception("Redis server is not available.")
    w.sub_client = rds.client().pubsub()
    w.pub_client = rds.client()
    w.init_config(option)
    w.close = False
    w.subscribe_thread.start()
    w.subscribe_event.wait(timeout=5)
    return w

```

It use `w.subscribe_thread.start()` to start a new thread, This can lead to a lot of mistakes!

You will see the follow error 

```text
cb=[_run_until_complete_cb() at C:\Python310\lib\asyncio\base_events.py:184]> got Future <Future pending> attached to a different loop
```

I modified the redis-watcher to async-redis-watcher, Solve these problems once and for all and support asynchronous calls.

## Installation

    pip install casbin_async_redis_watcher

## Simple Example

```python
import asyncio
import os
import casbin
from casbin_async_redis_watcher import new_watcher, WatcherOptions
from casbin import AsyncEnforcer
from functools import partial


async def update_policy(e: AsyncEnforcer, event):
    print("receive a new update policy....")
    print(event)
    await e.load_policy()


def get_examples(path):
    examples_path = os.path.split(os.path.realpath(__file__))[0] + "/../examples/"
    return os.path.abspath(examples_path + path)


async def make_async_casbin_watcher():
    test_option = WatcherOptions()
    test_option.host = "localhost"
    test_option.port = "6379"
    test_option.password = "password"
    test_option.channel = "test"
    test_option.db = 4
    test_option.ssl = False
    e = casbin.AsyncEnforcer(get_examples("rbac_model.conf"), get_examples("rbac_policy.csv"))
    func = partial(update_policy, e)
    test_option.optional_update_callback = func
    watcher = await new_watcher(test_option)
    e.set_watcher(watcher)
    await e.load_policy()
    return e


async def main():
    e = await make_async_casbin_watcher()
    await e.save_policy()
    await asyncio.sleep(2)
    await e.add_role_for_user("yangyanxing", "admin")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
    loop.run_forever()

```

In pycasbin, `casbin/async_internal_enforcer.py` line 114,

```python
 async def _add_policy(self, sec, ptype, rule):
    """async adds a rule to the current policy."""
    rule_added = self.model.add_policy(sec, ptype, rule)
    if not rule_added:
        return rule_added

    if self.adapter and self.auto_save:
        result = await self.adapter.add_policy(sec, ptype, rule)
        if result is False:
            return False

        if self.watcher and self.auto_notify_watcher:
            if callable(getattr(self.watcher, "update_for_add_policy", None)):
                self.watcher.update_for_add_policy(sec, ptype, rule)
            else:
                self.watcher.update()

    return rule_added
```

When call _add_policy function,_add_policies,save_policy and so on, if set watcher, will call `watcher.update_for_add_policy` or `watcher.update()` function.

But it's NOT use await, so, in this project, watcher.py, class RedisWatcher, the function `update` can't use async.

so I use loop.create_task for call the update function 

```python
def update(self):
    async def func():
        async with self.mutex:
            msg = MSG("Update", self.options.local_ID, "", "", "")
            return await self.pub_client.publish(self.options.channel, msg.marshal_binary())

    return self.loop.create_task(self.log_record(func))
```


## Getting Help

- [pycasbin](https://github.com/casbin/pycasbin)


## License

This project is under Apache 2.0 License. See the [LICENSE](LICENSE) file for the full license text.
