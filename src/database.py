import pyodbc


conn_str = 'Driver={ODBC Driver 18 for SQL Server};Server=tcp:acaciashotel.database.windows.net,1433;Database=Acacias_Hotel;Uid=ehiderg;Pwd=Andres30375670;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30'

conn = pyodbc.connect(conn_str)

