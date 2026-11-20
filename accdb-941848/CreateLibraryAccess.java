import com.healthmarketscience.jackcess.*;
import java.io.File;

public class CreateLibraryAccess {
  private static ColumnBuilder text(String name, int len) {
    return new ColumnBuilder(name, DataType.TEXT).setLength(len);
  }
  private static ColumnBuilder autoNumber(String name) {
    return new ColumnBuilder(name, DataType.LONG).setAutoNumber(true);
  }

  public static void main(String[] args) throws Exception {
    File f = new File("941848_БД_Библиотека.accdb");
    if (f.exists() && !f.delete()) throw new IllegalStateException("Cannot delete old file");

    try (Database db = DatabaseBuilder.create(Database.FileFormat.V2010, f)) {
      new TableBuilder("Читатель")
          .addColumn(autoNumber("Код читателя"))
          .addColumn(text("Фамилия", 50))
          .addColumn(text("Имя", 50))
          .addColumn(text("Домашний адрес", 255))
          .addColumn(text("Номер паспорта", 20))
          .addColumn(text("Телефон", 30))
          .setPrimaryKey("Код читателя")
          .toTable(db);

      new TableBuilder("Выдача")
          .addColumn(autoNumber("Код выдачи"))
          .addColumn(new ColumnBuilder("Код читателя", DataType.LONG))
          .addColumn(new ColumnBuilder("Код книги", DataType.LONG))
          .addColumn(new ColumnBuilder("Дата выдачи", DataType.SHORT_DATE_TIME))
          .addColumn(new ColumnBuilder("Дата возврата", DataType.SHORT_DATE_TIME))
          .addColumn(new ColumnBuilder("Рейтинг", DataType.INT))
          .setPrimaryKey("Код выдачи")
          .toTable(db);

      new TableBuilder("Книги")
          .addColumn(autoNumber("Код книги"))
          .addColumn(new ColumnBuilder("Код издательства", DataType.LONG))
          .addColumn(text("Название книги", 255))
          .addColumn(text("Автор", 150))
          .addColumn(new ColumnBuilder("Год издания", DataType.INT))
          .addColumn(new ColumnBuilder("Число страниц", DataType.INT))
          .addColumn(new ColumnBuilder("Цена", DataType.MONEY))
          .setPrimaryKey("Код книги")
          .toTable(db);

      new TableBuilder("Издательства")
          .addColumn(autoNumber("Код издательства"))
          .addColumn(text("Наименование издательства", 100))
          .addColumn(text("Город", 100))
          .addColumn(text("Телефон", 30))
          .addColumn(text("E-mail", 100))
          .addColumn(text("Сайт", 255))
          .setPrimaryKey("Код издательства")
          .toTable(db);
    }

    System.out.println("CREATED=" + f.getAbsolutePath());
    System.out.println("SIZE=" + f.length());
  }
}
