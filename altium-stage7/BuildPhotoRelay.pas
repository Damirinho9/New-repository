const
  OUT_DIR = 'C:\7330744_Altium\';
  SCH_DOC = 'C:\7330744_Altium\PhotoRelay_V6.SchDoc';
  PCB_DOC = 'C:\7330744_Altium\PhotoRelay_V6.PcbDoc';
  PRJ_DOC = 'C:\7330744_Altium\7330744_Variant6_PhotoRelay.PrjPcb';
  STATUS_FILE = 'C:\7330744_Altium\stage7-status.txt';
  BW = 100.0;
  BH = 70.0;

var
  Sch : ISch_Document;
  CurComp : ISch_Component;
  LogLines : TStringList;

procedure Log(S : String);
begin
  LogLines.Add(S);
  LogLines.SaveToFile(STATUS_FILE);
end;

procedure NewComp(Des, LibRef, Desc, Comment, FPName : String);
begin
  CurComp := SchServer.SchObjectFactory(eSchComponent, eCreate_Default);
  CurComp.CurrentPartID := 1;
  CurComp.DisplayMode := 0;
  CurComp.PartCount := 1;
  CurComp.LibReference := LibRef;
  CurComp.DesignItemId := LibRef;
  CurComp.ComponentDescription := Desc;
  CurComp.Designator.Text := Des;
  CurComp.Comment.Text := Comment;
end;

procedure CPin(Num, PName : String; Elec, Orient, X, Y, Len : Integer; ShowName : Boolean);
var Pin : ISch_Pin;
begin
  Pin := SchServer.SchObjectFactory(ePin, eCreate_Default);
  Pin.Designator := Num;
  Pin.Name := PName;
  Pin.Electrical := Elec;
  Pin.Orientation := Orient;
  Pin.Location := Point(MilsToCoord(X), MilsToCoord(Y));
  Pin.PinLength := MilsToCoord(Len);
  Pin.ShowName := ShowName;
  Pin.ShowDesignator := True;
  Pin.OwnerPartId := 1;
  Pin.OwnerPartDisplayMode := 0;
  CurComp.AddSchObject(Pin);
end;

procedure CRect(X1, Y1, X2, Y2 : Integer);
var R : ISch_Rectangle;
begin
  R := SchServer.SchObjectFactory(eRectangle, eCreate_Default);
  R.LineWidth := eSmall;
  R.Location := Point(MilsToCoord(X1), MilsToCoord(Y1));
  R.Corner := Point(MilsToCoord(X2), MilsToCoord(Y2));
  R.IsSolid := False;
  R.Color := $00800000;
  R.OwnerPartId := 1;
  R.OwnerPartDisplayMode := 0;
  CurComp.AddSchObject(R);
end;

procedure PlaceComp(X, Y : Integer; FPName : String);
var Impl : ISch_Implementation;
begin
  CurComp.Designator.IsHidden := False;
  CurComp.Designator.Location := Point(MilsToCoord(0), MilsToCoord(160));
  CurComp.Comment.IsHidden := False;
  CurComp.Comment.Location := Point(MilsToCoord(0), MilsToCoord(-260));
  Sch.RegisterSchObjectInContainer(CurComp);
  CurComp.MoveToXY(MilsToCoord(X), MilsToCoord(Y));
  Impl := CurComp.AddSchImplementation;
  Impl.ModelName := FPName;
  Impl.ModelType := 'PCBLIB';
  Impl.IsCurrent := True;
  Impl.UseComponentLibrary := False;
end;

procedure Wire(X1, Y1, X2, Y2 : Integer);
var W : ISch_Wire;
begin
  W := SchServer.SchObjectFactory(eWire, eCreate_GlobalCopy);
  W.InsertVertex := 1;
  W.SetState_Vertex(1, Point(MilsToCoord(X1), MilsToCoord(Y1)));
  W.InsertVertex := 2;
  W.SetState_Vertex(2, Point(MilsToCoord(X2), MilsToCoord(Y2)));
  Sch.RegisterSchObjectInContainer(W);
end;

procedure NetLbl(X, Y : Integer; T : String);
var N : ISch_NetLabel;
begin
  N := SchServer.SchObjectFactory(eNetlabel, eCreate_GlobalCopy);
  N.Location := Point(MilsToCoord(X), MilsToCoord(Y));
  N.Text := T;
  N.Orientation := eRotate0;
  Sch.RegisterSchObjectInContainer(N);
end;

procedure PPort(X, Y : Integer; T : String);
var P : ISch_PowerObject;
begin
  P := SchServer.SchObjectFactory(ePowerObject, eCreate_GlobalCopy);
  P.Location := Point(MilsToCoord(X), MilsToCoord(Y));
  P.Style := 4;
  P.Orientation := eRotate270;
  P.Text := T;
  P.ShowNetName := True;
  Sch.RegisterSchObjectInContainer(P);
end;

procedure Title(X, Y : Integer; T : String);
var L : ISch_Label;
begin
  L := SchServer.SchObjectFactory(eLabel, eCreate_GlobalCopy);
  L.Location := Point(MilsToCoord(X), MilsToCoord(Y));
  L.Text := T;
  L.Color := $00000080;
  Sch.RegisterSchObjectInContainer(L);
end;

procedure ConnectLeft(X, Y : Integer; Net : String);
begin
  Wire(X - 100, Y, X - 300, Y);
  NetLbl(X - 300, Y, Net);
end;

procedure ConnectRight(X, Y : Integer; Net : String);
begin
  Wire(X + 400, Y, X + 600, Y);
  NetLbl(X + 600, Y, Net);
end;

procedure ConnectLeft2(X, Y : Integer; Net : String);
begin
  Wire(X - 200, Y, X - 400, Y);
  NetLbl(X - 400, Y, Net);
end;

procedure ConnectRight2(X, Y : Integer; Net : String);
begin
  Wire(X + 700, Y, X + 900, Y);
  NetLbl(X + 900, Y, Net);
end;

procedure Add2(Des, LibRef, Val, FP, P1, P2, N1, N2 : String; X, Y : Integer);
begin
  NewComp(Des, LibRef, LibRef, Val, FP);
  CRect(100, 70, 200, -70);
  CPin('1', P1, eElectricPassive, eRotate180, 0, 0, 100, True);
  CPin('2', P2, eElectricPassive, eRotate0, 300, 0, 100, True);
  PlaceComp(X, Y, FP);
  ConnectLeft(X, Y, N1);
  ConnectRight(X, Y, N2);
end;

procedure Add3(Des, LibRef, Val, FP, P1, P2, P3, N1, N2, N3 : String; X, Y : Integer);
begin
  NewComp(Des, LibRef, LibRef, Val, FP);
  CRect(0, 100, 500, -200);
  CPin('1', P1, eElectricPassive, eRotate180, 0, 0, 200, True);
  CPin('2', P2, eElectricPassive, eRotate0, 500, 0, 200, True);
  CPin('3', P3, eElectricPassive, eRotate180, 0, -100, 200, True);
  PlaceComp(X, Y, FP);
  ConnectLeft2(X, Y, N1);
  ConnectRight2(X, Y, N2);
  ConnectLeft2(X, Y - 100, N3);
end;

procedure Add4(Des, LibRef, Val, FP, P1, P2, P3, P4, N1, N2, N3, N4 : String; X, Y : Integer);
begin
  NewComp(Des, LibRef, LibRef, Val, FP);
  CRect(0, 100, 500, -250);
  CPin('1', P1, eElectricPassive, eRotate180, 0, 0, 200, True);
  CPin('2', P2, eElectricPassive, eRotate180, 0, -100, 200, True);
  CPin('3', P3, eElectricPassive, eRotate0, 500, 0, 200, True);
  CPin('4', P4, eElectricPassive, eRotate0, 500, -100, 200, True);
  PlaceComp(X, Y, FP);
  ConnectLeft2(X, Y, N1);
  ConnectLeft2(X, Y - 100, N2);
  ConnectRight2(X, Y, N3);
  ConnectRight2(X, Y - 100, N4);
end;

procedure Add5(Des, LibRef, Val, FP, N1, N2, N3, N4, N5 : String; X, Y : Integer);
begin
  NewComp(Des, LibRef, LibRef, Val, FP);
  CRect(0, 100, 500, -500);
  CPin('1', 'SW', eElectricPassive, eRotate180, 0, 0, 200, True);
  CPin('2', 'LOAD_L', eElectricPassive, eRotate180, 0, -100, 200, True);
  CPin('3', 'MAINS_L', eElectricPassive, eRotate180, 0, -200, 200, True);
  CPin('4', 'MAINS_N', eElectricPassive, eRotate180, 0, -300, 200, True);
  CPin('5', 'CASE', eElectricPassive, eRotate180, 0, -400, 200, True);
  PlaceComp(X, Y, FP);
  ConnectLeft2(X, Y, N1);
  ConnectLeft2(X, Y - 100, N2);
  ConnectLeft2(X, Y - 200, N3);
  ConnectLeft2(X, Y - 300, N4);
  ConnectLeft2(X, Y - 400, N5);
end;

procedure BuildSchematic;
var Doc : IServerDocument;
begin
  Log('SCH_BEGIN');
  if SchServer = nil then Client.StartServer('SCH');
  Doc := Client.GetDocumentByPath(SCH_DOC);
  if Doc <> nil then Client.CloseDocument(Doc);
  if FileExists(SCH_DOC) then DeleteFile(SCH_DOC);
  Doc := CreateNewDocumentFromDocumentKind('SCH');
  if Doc = nil then begin Log('ERROR=SCH_NEW_FAILED'); Exit; end;
  Doc.DoSafeChangeFileNameAndSave(SCH_DOC, 'SCH');
  Client.ShowDocument(Doc);
  Sch := SchServer.GetSchDocumentByPath(SCH_DOC);
  if Sch = nil then begin Log('ERROR=SCH_OPEN_FAILED'); Exit; end;
  Sch.SheetStyle := eSheetA1;
  SchServer.ProcessControl.PreProcess(Sch, '');

  Title(600, 21200, '7330744 Variant 6 - Photo Relay');
  Title(600, 20950, 'Educational schematic rebuilt natively in Altium Designer');
  Title(600, 20700, 'COM = control common reference; power section is an educational equivalent.');

  Add2('R1','RES','4.7 MOhm','R_1206','1','2','U_CTRL','N_R1',1200,19800);
  Add2('R2','RES','47 kOhm','R_1206','1','2','N_R1','SENS',2800,19800);
  Add2('VD1','PHOTODIODE','FD320','DIODE_THT','A','K','COM','SENS',4400,19800);
  Add2('C1','CAP_POL','K50-35 0.47uF model','CAP_RADIAL','-','+','COM','SENS',6000,19800);
  Add2('C2','CAP','K73 0.1uF model','C_1206','1','2','U_CTRL','COM',7600,19800);
  Add2('VD2','ZENER','KS512A ~12V','DIODE_THT','A','K','COM','U_CTRL',9200,19800);

  Add3('VT1','NMOS','KP501A','SOT23','D','S','G','SENS','T1','G12',1200,18100);
  Add2('R3','RES','330 Ohm','R_0805','1','2','G12','COM',3100,18100);
  Add2('R4','RES','10 kOhm','R_0805','1','2','U_CTRL','T1',4700,18100);
  Add3('VT2','NMOS','KP501A','SOT23','D','S','G','T1','T2','G12',6300,18100);
  Add2('R5','RES','5.1 kOhm','R_0805','1','2','U_CTRL','T2',8200,18100);
  Add3('VT3','NMOS_POWER','KP707B2','TO220_3','D','S','G','T2','VT3_R6','COM',9800,18100);
  Add2('R6','RES','51 Ohm','R_1206','1','2','VT3_R6','DRV',11700,18100);

  Add2('R7','RES','58 kOhm','R_1206','1','2','L','LED_R',1200,16300);
  Add2('VD3','DIODE','KD243ZH','DIODE_THT','A','K','LED_R','LED_A',2800,16300);
  Add2('HL1','LED','L383SRWT','LED_THT','A','K','LED_A','U_CTRL',4400,16300);
  Add2('RU1','VARISTOR','FNR-20K391','VAR20','1','2','DRV','COM',6000,16300);
  Add2('FU1','FUSE','32 A','FUSE_THT','1','2','DRV','BR_A',7600,16300);
  Add4('VD6','BRIDGE','RB154','BRIDGE4','~1','~2','+','-','BR_A','COM','G1','G2',9200,16300);

  Add2('R8','RES','56 Ohm','R_1206','1','2','G1','COM',1200,14500);
  Add2('VD4','DIODE','KD243ZH','DIODE_THT','A','K','COM','G1',2800,14500);
  Add3('VS1','SCR','T123-250','SCR_EXT3','A','K','G','SW','COM','G1',4400,14500);
  Add2('R9','RES','56 Ohm','R_1206','1','2','G2','SW',6400,14500);
  Add2('VD5','DIODE','KD243ZH','DIODE_THT','A','K','SW','G2',8000,14500);
  Add3('VS2','SCR','T123-250','SCR_EXT3','A','K','G','COM','SW','G2',9600,14500);

  Add2('C3','CAP','K73 0.047uF model','C_FILM','1','2','L','COM',1200,12600);
  Add2('FU2','FUSE','32 A','FUSE_THT','1','2','COM','N',3100,12600);
  Add5('XP1','CONN5','MRN-5Sh 5-pin','CONN5_THT','SW','L','L','N','CASE',5200,12800);

  PPort(9000,12600,'COM');
  Title(10400,12600,'XP1.5 CASE/SERVICE - verify against original assembly');
  Title(10400,12350,'VS1/VS2 represented as external high-current devices.');
  Title(10400,12100,'Not a fabrication-ready 220 V / tens-of-kW design.');

  SchServer.ProcessControl.PostProcess(Sch, '');
  Sch.GraphicallyInvalidate;
  Doc.Modified := True;
  Doc.DoFileSave('');
  Log('SCH_SAVED');
end;

procedure SetOutlinePoint(O : IPCB_BoardOutline; I : Integer; X, Y : Double);
var S : TPolySegment;
begin
  S := O.Segments[I];
  S.Kind := ePolySegmentLine;
  S.vx := MMsToCoord(X);
  S.vy := MMsToCoord(Y);
  O.Segments[I] := S;
end;

procedure AddHole(Board : IPCB_Board; X, Y : Double; N : Integer);
var Pad : IPCB_Pad;
begin
  Pad := PCBServer.PCBObjectFactory(ePadObject,eNoDimension,eCreate_Default);
  Pad.X := MMsToCoord(X); Pad.Y := MMsToCoord(Y);
  Pad.Layer := eMultiLayer;
  Pad.TopXSize := MMsToCoord(3.2); Pad.TopYSize := MMsToCoord(3.2);
  Pad.MidXSize := MMsToCoord(3.2); Pad.MidYSize := MMsToCoord(3.2);
  Pad.BotXSize := MMsToCoord(3.2); Pad.BotYSize := MMsToCoord(3.2);
  Pad.TopShape := eRounded;
  Pad.HoleSize := MMsToCoord(3.2);
  Pad.Plated := False;
  Pad.Name := 'MH' + IntToStr(N);
  Pad.Moveable := False;
  Board.AddPCBObject(Pad);
end;

procedure AddCompPad(Comp : IPCB_Component; PX, PY : Integer; PadName : String; Thru : Boolean);
var P : IPCB_Pad;
begin
  P := PCBServer.PCBObjectFactory(ePadObject,eNoDimension,eCreate_Default);
  P.Name := PadName;
  P.X := MilsToCoord(PX); P.Y := MilsToCoord(PY);
  if Thru then begin
    P.Layer := eMultiLayer;
    P.TopShape := eRounded;
    P.TopXSize := MilsToCoord(90); P.TopYSize := MilsToCoord(90);
    P.MidXSize := MilsToCoord(90); P.MidYSize := MilsToCoord(90);
    P.BotXSize := MilsToCoord(90); P.BotYSize := MilsToCoord(90);
    P.HoleSize := MilsToCoord(35);
  end else begin
    P.Layer := eTopLayer; P.Mode := ePadMode_Simple; P.HoleSize := 0;
    P.TopShape := eRectangular;
    P.TopXSize := MilsToCoord(80); P.TopYSize := MilsToCoord(55);
  end;
  Comp.AddPCBObject(P);
  PCBServer.SendMessageToRobots(Comp.I_ObjectAddress,c_Broadcast,PCBM_BoardRegisteration,P.I_ObjectAddress);
end;

procedure AddCompSilk(Comp : IPCB_Component; X1, Y1, X2, Y2 : Integer);
var T : IPCB_Track;
begin
  T := PCBServer.PCBObjectFactory(eTrackObject,eNoDimension,eCreate_Default);
  T.X1 := MilsToCoord(X1); T.Y1 := MilsToCoord(Y1);
  T.X2 := MilsToCoord(X2); T.Y2 := MilsToCoord(Y2);
  T.Width := MilsToCoord(8); T.Layer := eTopOverlay;
  Comp.AddPCBObject(T);
  PCBServer.SendMessageToRobots(Comp.I_ObjectAddress,c_Broadcast,PCBM_BoardRegisteration,T.I_ObjectAddress);
end;

procedure AddPCBComp(Board : IPCB_Board; Des, Val, Pattern : String; Xmm, Ymm : Double; Pins : Integer; Thru : Boolean);
var C : IPCB_Component; i, StartX, Pitch, PX : Integer;
begin
  PCBServer.PreProcess;
  C := PCBServer.PCBObjectFactory(eComponentObject,eNoDimension,eCreate_Default);
  if C = nil then begin PCBServer.PostProcess; Exit; end;
  C.X := MMsToCoord(Xmm); C.Y := MMsToCoord(Ymm); C.Layer := eTopLayer;
  C.SourceDesignator := Des; C.Pattern := Pattern;
  C.NameOn := True; C.Name.Text := Des;
  C.CommentOn := True; C.Comment.Text := Val;
  Pitch := 100; StartX := -((Pins - 1) * Pitch) div 2;
  for i := 1 to Pins do begin
    PX := StartX + (i - 1) * Pitch;
    AddCompPad(C,PX,0,IntToStr(i),Thru);
  end;
  AddCompSilk(C,StartX-70,-100,-StartX+70,-100);
  AddCompSilk(C,-StartX+70,-100,-StartX+70,100);
  AddCompSilk(C,-StartX+70,100,StartX-70,100);
  AddCompSilk(C,StartX-70,100,StartX-70,-100);
  Board.AddPCBObject(C);
  PCBServer.SendMessageToRobots(Board.I_ObjectAddress,c_Broadcast,PCBM_BoardRegisteration,C.I_ObjectAddress);
  PCBServer.PostProcess;
end;

procedure BuildPCB;
var Doc : IServerDocument; Board : IPCB_Board; O : IPCB_BoardOutline;
begin
  Log('PCB_BEGIN');
  if FileExists(PCB_DOC) then DeleteFile(PCB_DOC);
  Doc := CreateNewDocumentFromDocumentKind('PCB');
  if Doc = nil then begin Log('ERROR=PCB_NEW_FAILED'); Exit; end;
  Doc.DoSafeChangeFileNameAndSave(PCB_DOC,'PCB');
  Client.ShowDocument(Doc);
  Board := PCBServer.GetCurrentPCBBoard;
  if Board = nil then begin Log('ERROR=PCB_OPEN_FAILED'); Exit; end;

  PCBServer.PreProcess;
  O := Board.BoardOutline; O.Invalidate; O.PointCount := 4;
  SetOutlinePoint(O,0,0,0); SetOutlinePoint(O,1,BW,0);
  SetOutlinePoint(O,2,BW,BH); SetOutlinePoint(O,3,0,BH);
  O.Rebuild; O.Validate;
  PCBServer.PostProcess;

  AddHole(Board,4,4,1); AddHole(Board,96,4,2); AddHole(Board,4,66,3); AddHole(Board,96,66,4);
  AddPCBComp(Board,'R1','4.7M','R_1206',12,60,2,False);
  AddPCBComp(Board,'R2','47k','R_1206',24,60,2,False);
  AddPCBComp(Board,'VD1','FD320','DIODE_THT',36,60,2,True);
  AddPCBComp(Board,'C1','K50-35','CAP_RADIAL',48,60,2,True);
  AddPCBComp(Board,'C2','K73','C_1206',60,60,2,False);
  AddPCBComp(Board,'VD2','KS512A','DIODE_THT',72,60,2,True);
  AddPCBComp(Board,'VT1','KP501A','SOT23',12,49,3,False);
  AddPCBComp(Board,'R3','330','R_0805',24,49,2,False);
  AddPCBComp(Board,'R4','10k','R_0805',36,49,2,False);
  AddPCBComp(Board,'VT2','KP501A','SOT23',48,49,3,False);
  AddPCBComp(Board,'R5','5.1k','R_0805',60,49,2,False);
  AddPCBComp(Board,'VT3','KP707B2','TO220_3',74,49,3,True);
  AddPCBComp(Board,'R6','51','R_1206',86,49,2,False);
  AddPCBComp(Board,'R7','58k','R_1206',12,38,2,False);
  AddPCBComp(Board,'VD3','KD243ZH','DIODE_THT',24,38,2,True);
  AddPCBComp(Board,'HL1','L383SRWT','LED_THT',36,38,2,True);
  AddPCBComp(Board,'RU1','FNR-20K391','VAR20',48,38,2,True);
  AddPCBComp(Board,'FU1','32A','FUSE_THT',62,38,2,True);
  AddPCBComp(Board,'VD6','RB154','BRIDGE4',76,38,4,True);
  AddPCBComp(Board,'R8','56','R_1206',12,27,2,False);
  AddPCBComp(Board,'VD4','KD243ZH','DIODE_THT',24,27,2,True);
  AddPCBComp(Board,'VS1','T123-250','SCR_EXT3',40,27,3,True);
  AddPCBComp(Board,'R9','56','R_1206',56,27,2,False);
  AddPCBComp(Board,'VD5','KD243ZH','DIODE_THT',68,27,2,True);
  AddPCBComp(Board,'VS2','T123-250','SCR_EXT3',84,27,3,True);
  AddPCBComp(Board,'C3','K73','C_FILM',14,15,2,True);
  AddPCBComp(Board,'FU2','32A','FUSE_THT',30,15,2,True);
  AddPCBComp(Board,'XP1','MRN-5Sh','CONN5_THT',52,15,5,True);

  Board.ViewManager_FullUpdate;
  Doc.Modified := True; Doc.DoFileSave('');
  Log('PCB_SAVED');
end;

procedure BuildProject;
var L : TStringList; WS : IWorkspace; P : IProject; D : IServerDocument; COK : Boolean;
begin
  Log('PROJECT_BEGIN');
  if FileExists(PRJ_DOC) then DeleteFile(PRJ_DOC);
  L := TStringList.Create; L.Add('[Design]'); L.Add('Version=1.0'); L.SaveToFile(PRJ_DOC); L.Free;
  ResetParameters; AddStringParameter('ObjectKind','Project'); AddStringParameter('FileName',PRJ_DOC);
  RunProcess('WorkspaceManager:OpenObject'); Sleep(1500);
  WS := GetWorkspace; P := WS.DM_FocusedProject;
  if P = nil then begin Log('ERROR=PROJECT_OPEN_FAILED'); Exit; end;
  P.DM_AddSourceDocument(SCH_DOC); P.DM_AddSourceDocument(PCB_DOC);
  ResetParameters; AddStringParameter('ObjectKind','Project'); RunProcess('WorkspaceManager:SaveObject');
  Sleep(800);
  COK := P.DM_Compile;
  Log('PROJECT_COMPILE=' + BoolToStr(COK,True));
  Log('PROJECT_DOCS=' + IntToStr(P.DM_LogicalDocumentCount));
  D := Client.OpenDocument('SCH',SCH_DOC);
  if D <> nil then Client.ShowDocument(D);
  Log('SUCCESS=1');
end;

procedure Run;
begin
  ForceDirectories(OUT_DIR);
  LogLines := TStringList.Create;
  try
    Log('STAGE7_BEGIN');
    BuildSchematic;
    if not FileExists(SCH_DOC) then begin Log('ERROR=SCH_FILE_MISSING'); Exit; end;
    BuildPCB;
    if not FileExists(PCB_DOC) then begin Log('ERROR=PCB_FILE_MISSING'); Exit; end;
    BuildProject;
    if FileExists(PRJ_DOC) then Log('PRJ_EXISTS=1') else Log('PRJ_EXISTS=0');
    if FileExists(SCH_DOC) then Log('SCH_EXISTS=1') else Log('SCH_EXISTS=0');
    if FileExists(PCB_DOC) then Log('PCB_EXISTS=1') else Log('PCB_EXISTS=0');
  finally
    LogLines.SaveToFile(STATUS_FILE);
    LogLines.Free;
  end;
end;
