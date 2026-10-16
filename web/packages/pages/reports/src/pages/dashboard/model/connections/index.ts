import { sample } from "effector";

import { pageMounted, periodChanged } from "../events/index.ts";
import { $period } from "../stores/index.ts";

sample({ clock: periodChanged, target: $period });
$period.reset(pageMounted);
