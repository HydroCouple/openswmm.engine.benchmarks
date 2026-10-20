# Analytic multispecies verification

Engine: `175b5fae-dirty`

Equal-unit parent/product conversion in an isolated wet pool. A(t) = exp(-kt), B(t) = 1 - A(t).
Each case checks every native reporting period at the storage node and conduit, including the sum A+B.

| Case | Quality solver | Result | Maximum concentration error | Sum error |
| --- | --- | --- | --- | --- |
| parent_product_SEC | LEGACY | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_SEC_override | LEGACY | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_MIN | LEGACY | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_MIN_override | LEGACY | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_HR | LEGACY | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_HR_override | LEGACY | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_DAY | LEGACY | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_DAY_override | LEGACY | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_SEC | EULERIAN_ARD | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_SEC_override | EULERIAN_ARD | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_MIN | EULERIAN_ARD | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_MIN_override | EULERIAN_ARD | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_HR | EULERIAN_ARD | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_HR_override | EULERIAN_ARD | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_DAY | EULERIAN_ARD | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_DAY_override | EULERIAN_ARD | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_SEC | LAGRANGIAN | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_SEC_override | LAGRANGIAN | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_MIN | LAGRANGIAN | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_MIN_override | LAGRANGIAN | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_HR | LAGRANGIAN | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_HR_override | LAGRANGIAN | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |
| parent_product_DAY | LAGRANGIAN | PASS | 4.145811415534606e-05 | 2.9802322387695312e-08 |
| parent_product_DAY_override | LAGRANGIAN | PASS | 8.25005962779013e-05 | 2.9802322387695312e-08 |

Tolerance: 5e-4 concentration units; 2e-6 for A+B. RATE_UNITS variants have the same physical rate.
The override cases double Tank k and halve Pipe k. They must therefore have different analytic curves.
This suite does not qualify porous layers, wall geometry, runoff reactors, or checkpoint/output continuation.
