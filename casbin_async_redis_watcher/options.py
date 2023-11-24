# -*- coding: utf-8 -*-
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import uuid


class WatcherOptions:
    password = None
    host = "localhost"
    port = "6379"
    db = 0
    use_pool = True
    ssl = False
    sub_client = None
    pub_client = None
    channel = None
    ignore_self = None
    local_ID = None
    optional_update_callback = None

    def init_config(self):

        if self.local_ID is None:
            self.local_ID = str(uuid.uuid4())

        if self.channel is None:
            self.channel = "/casbin"