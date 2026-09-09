### **The Problem**

In NEV files, our primary focus is on decoding the **serial number** from digital events. This serial is reconstructed from groups of 5 bytes (`UnparsedData` values), each encoding 7 bits of data.

However, **discontinuities** can occur when these groups are incomplete—i.e., a group contains fewer than 5 bytes, breaking the encoding logic.

---

### **Examples**

Below is a snippet from a NEV digital events dataframe:

{{ read_csv('discontinuity-in-nev/digital_events_small.csv') }}

In this example, a valid group of 5 bytes appears:

```
43, 76, 35, 0, 0
```

Then suddenly, only 2 values are available:

```
76, 0
```

which suggests we were expecting:

```
44, 76, 35, 0, 0
```

In the next group, the structure resumes normally:

```
45, 76, 35, 0, 0
```

Another example:

{{ read_csv('discontinuity-in-nev/digital_events_small_2.csv') }}

Here, we observe valid serial byte groups:

```
96, 101, 35, 0, 0
97, 101, 35, 0, 0
```

Then we lose one byte (98 is missing):

```
101, 35, 0, 0
```

---

### **Observations**

- Missing values can occur **at any byte position** within the expected 5-byte group.
- The NEV file logs digital events only on **bit changes**, so dropped or missing bytes **cannot be recovered** based solely on timing.

---

### **Solution**

Since it's not possible to recover partial serial groups, we:

1. Extract only the **valid 5-byte groups** using `pyvideosync.nev.get_cleaned_digital_events_df`.
2. Reconstruct serial values from these clean groups using `bits_to_decimal`.
3. Apply **gap-filling logic** to infer missing serial numbers using:

```python
from pyvideosync.utils import fill_missing_serials_with_gap
```

Refer to the function `get_chunk_serial_df()` in `pyvideosync.nev` for the full reconstruction pipeline.

---

### **Download**

- [`digital_events_df.csv`](discontinuity-in-nev/digital_events_df.csv)
- [`NSP1-20240416-164732-001.nev`](discontinuity-in-nev/NSP1-20240416-164732-001.nev)
