import com.healthmarketscience.jackcess.*;
import java.io.File;
import java.security.MessageDigest;
import java.nio.file.Files;
import java.util.*;

public class VerifyLibraryAccess {
  private static String hex(byte[] b) {
    StringBuilder s = new StringBuilder();
    for (byte x : b) s.append(String.format("%02x", x));
    return s.toString();
  }

  public static void main(String[] args) throws Exception {
    File f = new File("941848_БД_Библиотека.accdb");
    if (!f.isFile() || f.length() == 0) throw new IllegalStateException("ACCDB missing/empty");

    MessageDigest md = MessageDigest.getInstance("SHA-256");
    System.out.println("FILE=" + f.getName());
    System.out.println("SIZE=" + f.length());
    System.out.println("SHA256=" + hex(md.digest(Files.readAllBytes(f.toPath()))));

    List<String> expected = Arrays.asList("Читатель", "Выдача", "Книги", "Издательства");
    try (Database db = DatabaseBuilder.open(f)) {
      System.out.println("FORMAT=" + db.getFileFormat());
      Set<String> names = db.getTableNames();
      for (String n : expected) if (!names.contains(n)) throw new IllegalStateException("Missing table: " + n);
      System.out.println("TABLES_OK=" + expected);

      for (String n : expected) {
        Table t = db.getTable(n);
        System.out.println("TABLE=" + n);
        boolean hasPk = false;
        for (Column c : t.getColumns()) {
          System.out.println("  COLUMN=" + c.getName() + "|TYPE=" + c.getType() + "|AUTONUMBER=" + c.isAutoNumber());
        }
        for (Index idx : t.getIndexes()) {
          System.out.println("  INDEX=" + idx.getName() + "|PRIMARY=" + idx.isPrimaryKey() + "|COLS=" + idx.getColumns());
          if (idx.isPrimaryKey()) hasPk = true;
        }
        if (!hasPk) throw new IllegalStateException("Missing PK: " + n);
      }
    }
    System.out.println("VERIFY=OK");
  }
}
