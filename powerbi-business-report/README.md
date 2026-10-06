# Load the sales report into Power BI

This guide builds a report from the Parquet file exported by ADF. The repository does not include a generated `.pbix` or automate Power BI publication. Run Power BI Desktop on Windows; the local provisioning commands can be run on another machine.

## 1. Produce and locate the Azure report

Complete [setup and deployment](../README.md#setup-and-run-from-your-local-machine), then run from the repository root:

```bash
uv run solution run-adf
```

Wait for success. In Azure Portal, open the storage account named by `STORAGE_ACCOUNT` in the root `.env`. Under **Containers**, open `reports`, then `sales`, and confirm `report.parquet` exists with a recent last-modified time.

The file URL is:

```text
https://<STORAGE_ACCOUNT>.blob.core.windows.net/reports/sales/report.parquet
```

Replace `<STORAGE_ACCOUNT>` with your account name. Do not use the Databricks `/Volumes/` path or the unused Azure `lakehouse` container. Running the notebook manually does not perform the Azure copy. See the [ADF walkthrough](../azure-data-factory-pipeline/README.md#how-the-sales-export-works).

## 2. Connect from Power BI Desktop

1. Select **Home → Get data → More → Parquet**.
2. Enter the full report URL above and select **OK**.
3. Choose **Account key**. An authorized instructor can obtain the storage key from Azure Portal → storage account → **Access keys**. Enter the key in the credential dialog, not in the URL or a query.
4. Connect and choose **Transform Data**. Rename the query to `SalesReport`.

Microsoft documents this direct Azure URL workflow in the [Parquet connector guide](https://learn.microsoft.com/en-us/power-query/connectors/parquet). The connector imports data; a refreshed Azure file does not immediately update an already imported model.

The account key belongs to this dedicated demo storage account; it is not `AZURE_CLIENT_SECRET` or `DATABRICKS_TOKEN`. Students without access to the key should request an instructor-provided connection credential rather than change infrastructure configuration.

### Alternative: browse with Azure Blob Storage

Select **Get data → Azure → Azure Blob Storage**, enter the account name or `https://<STORAGE_ACCOUNT>.blob.core.windows.net`, and authenticate. Select `reports` in Navigator and choose **Transform Data**. Filter the file listing to the exact `sales/report.parquet` path, then open its **Content** binary to parse the Parquet data. Do not load only the blob metadata or combine unrelated files.

The [Azure Blob Storage connector](https://learn.microsoft.com/en-us/power-query/connectors/azure-blob-storage) also supports organizational account authentication. If using that option, your signed-in identity needs storage data access; the repository's deployment Contributor role alone does not grant that access. The tutorial's existing account-key route requires no additional role assignment.

## 3. Check columns and expected results

In Power Query, confirm the following types, then select **Close & Apply**:

| Column | Power BI type | Meaning |
|---|---|---|
| `sale_date` | Date | Date shared by the sales in this group |
| `category` | Text | Cleaned, lowercase category |
| `units` | Whole number | Sum of quantities |
| `revenue` | Fixed decimal number | Sum of quantity × unit price |
| `sale_count` | Whole number | Number of source sales in the group |

The unchanged repository fixture produces:

| sale_date | category | units | revenue | sale_count |
|---|---|---:|---:|---:|
| 2026-01-01 | books | 25 | 250.00 | 5 |
| 2026-01-01 | electronics | 30 | 300.00 | 5 |
| **Total** | | **55** | **550.00** | **10** |

Row order is not significant. This export has one row per date and category, so it contains **two rows**, representing **ten sales**. Product and individual sale IDs are not present. No relationships or date table are needed for this single-date exercise.

## 4. Create measures and visuals

Select **New measure** and create each measure separately:

```dax
Total Revenue = SUM(SalesReport[revenue])
```

```dax
Total Units = SUM(SalesReport[units])
```

```dax
Total Sales = SUM(SalesReport[sale_count])
```

```dax
Revenue per Sale = DIVIDE([Total Revenue], [Total Sales])
```

Use `Total Sales`, not `COUNTROWS(SalesReport)`, to count original sales. Format revenue measures with two decimal places; the fixture does not specify a currency.

Build a first report page with:

- Three cards for `Total Revenue`, `Total Units`, and `Total Sales`.
- A column chart with `category` on the horizontal axis and `Total Revenue` as its value.
- A table with `sale_date`, `category`, and the three totals.
- A category slicer to demonstrate filtering.

With no filters, the cards should show **550.00**, **55**, and **10**, and `Revenue per Sale` should be **55.00**. Selecting `books` should show **250.00**, **25**, and **5**. Save the report as `sales-report.pbix` in your chosen local location.

## 5. Publish and refresh

If your Power BI account has permission to publish to the target workspace, sign in to Desktop and select **Publish**. In Power BI service, open the published semantic model's **Settings**, configure its cloud connection or data-source credentials, and run **Refresh now**. Desktop credentials are not a substitute for configuring service access. See [Microsoft's refresh setup guide](https://learn.microsoft.com/en-us/power-bi/connect-data/refresh-scheduled-refresh).

For repeated use, configure a refresh schedule after the expected ETL completion time and check refresh history. A fixed schedule does not wait for ADF or verify that it succeeded. For this course, the clearest sequence is:

```text
Run ADF → confirm copy succeeded → refresh Power BI → check report totals
```

The repository creates neither an ADF schedule nor a Power BI refresh integration. Automating refresh directly after ADF would require an additional integration.

The URL source avoids depending on a downloaded local file. Restricted storage networks may need gateway configuration; consult the [Blob connector's network limitations](https://learn.microsoft.com/en-us/power-query/connectors/azure-blob-storage#limitations-and-considerations) if service refresh fails despite a successful Desktop connection. Sharing reports depends on the workspace and your organization's Power BI licensing and permissions.

## Troubleshooting

| Problem | Check |
|---|---|
| File not found | Exact storage account, `reports` container, `sales/report.parquet` path, and successful ADF copy. |
| Authentication fails | Use the Azure storage credential, not the Databricks token. In Desktop's **Data source settings**, edit or clear stale credentials and reconnect. |
| Organizational account cannot read data | Ask the administrator to verify storage data permissions for that identity. Azure management Contributor access is not equivalent to blob read access. |
| Preview shows names and binary values | You are viewing the storage file listing. Open the report's Content binary, or use the direct Parquet connector. |
| Parquet streamed-binary error | Use the documented Parquet connector with the Azure Blob URL instead of a generic Web query. |
| Sales count is 2 | You counted summary rows. Sum `sale_count` to get 10 source sales. |
| Totals are wrong | Clear report filters, verify numeric types, compare the two rows above, and check whether the fixture was changed. |
| Data remains unchanged | ADF reuses the staged source. Update the repository fixture and notebook assertions, redeploy, run ADF, then refresh Power BI. |
| Desktop works but service refresh fails | Check service connection credentials, refresh history, and storage network accessibility. |
| Report stops refreshing after cleanup | Azure cleanup deletes the source storage account. Disable its Power BI refresh schedule and remove or repoint the published model. |

This procedure is a student exercise to run against your deployed resources. Local provisioning tests do not validate Power BI connections or service refresh.
