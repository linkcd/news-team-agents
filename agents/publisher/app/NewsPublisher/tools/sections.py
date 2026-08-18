# Copyright 2026 news-agent contributors
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

SECTION_MAP = {
    "domestic": "国内新闻",
    "international": "国际新闻",
    "business": "财经新闻",
}

SECTION_ORDER = ["domestic", "international", "business"]

REVERSE_SECTION_MAP = {v: k for k, v in SECTION_MAP.items()}
