Attribute VB_Name = "ModFlashRancho"
'==============================================================================
' FLASH RANCHO - Posidonia Shipping / OPS FIN
'
' Ciclo completo de uma antecipação (recarga Flash) de rancho:
'   Etapa 1 - Flash1_SolicitarRecarga
'             Selecione o e-mail "Solicitação de Depósito" da operação e rode.
'             Monta o e-mail de SOLICITAÇÃO DE RECARGA FLASH para a Jessica,
'             com a RQA anexada.
'   Etapa 2 - Flash2_PrestarContasDanfes
'             Selecione o e-mail da SOLICITAÇÃO DE RECARGA FLASH e rode.
'             Lê a pasta da recarga, confere DANFE x PO, calcula o saldo e
'             monta o encaminhamento para Protocolo, Contas a Pagar, Will e
'             Sanchez com todas as DANFEs e POs anexadas.
'
' Nenhum e-mail é enviado automaticamente: o e-mail abre para conferência
' e o envio é sempre manual (botão Enviar).
'==============================================================================
Option Explicit

'------------------------------- CONFIGURAÇÃO ---------------------------------
' Pasta base das recargas. Estrutura sugerida:
'   C:\FLASH\ACR26017\RQA110686\  (DANFEs + POs daquela recarga)
' O log FLASH_LOG.csv fica nesta pasta.
Private Const PASTA_RAIZ As String = "C:\FLASH"
Private Const ARQ_LOG As String = "FLASH_LOG.csv"

Private Const NOME_REMETENTE As String = "Mario"      ' aparece em "Jessica/Mario, bom dia!"
Private Const PORTADOR_PADRAO As String = "THIAGO"
Private Const CARTAO_PADRAO As String = "85866820"
Private Const DIAS_LIBERACAO As Long = 7              ' liberação = ETB + 1 dia, por 7 dias
Private Const ENVIAR_COMO_OPSFIN As Boolean = True    ' envia em nome da caixa OPS FIN

Private Const EMAIL_JESSICA As String = "jpm@posidonia.com.br"
Private Const EMAIL_PROTOCOLO As String = "protocolofiscal@posidoniashipping.com"
Private Const EMAIL_CONTAS As String = "contasapagar@posidoniashipping.com"
Private Const EMAIL_WILL As String = "wbl@posidoniashipping.com"
Private Const EMAIL_SANCHEZ As String = "lss@posidoniashipping.com"
Private Const EMAIL_OPSFIN As String = "ops.fin@posidoniashipping.com"

Private Const TITULO As String = "Flash Rancho"
Private Const FONTE As String = "font-family:Aptos,Calibri,sans-serif;font-size:11pt;color:#000000"


'==============================================================================
' ETAPA 1 - SOLICITAÇÃO DE RECARGA
'==============================================================================
Public Sub Flash1_SolicitarRecarga()
    Dim m As Outlook.MailItem
    Set m = ItemSelecionado()
    If m Is Nothing Then
        MsgBox "Selecione (um clique) o e-mail de 'Solicitação de Depósito' enviado pela operação e rode de novo.", vbExclamation, TITULO
        Exit Sub
    End If

    Dim assunto As String, corpo As String
    assunto = LimparAssunto(m.Subject)
    corpo = m.Body

    ' --- viagem / navio / referência
    Dim viagem As String, navio As String, referencia As String
    viagem = UCase$(Pergunta("Viagem:", ExtrairViagem(assunto)))
    If viagem = "" Then Exit Sub
    navio = UCase$(Pergunta("Navio:", NavioPorViagem(viagem)))
    If navio = "" Then Exit Sub

    If InStr(1, assunto, "COMPLEMENTAR", vbTextCompare) > 0 Then
        referencia = "RANCHO COMPLEMENTAR"
    Else
        referencia = "RANCHO MENSAL"
    End If
    referencia = UCase$(Pergunta("Referência da recarga:", referencia & " " & UCase$(UltimaPalavra(assunto))))
    If referencia = "" Then Exit Sub

    ' --- valores
    Dim txtPedido As String, txt As String, vRecarga As Double
    txtPedido = ExtrairNumeroApos(corpo, "R$")
    txt = Pergunta("Valor pedido pela operação: R$ " & txtPedido & vbCrLf & vbCrLf & _
                   "Informe o valor da RECARGA (ex.: 25.000,00):", txtPedido)
    If txt = "" Then Exit Sub
    vRecarga = ParaNumero(txt)
    If vRecarga <= 0 Then
        MsgBox "Valor de recarga inválido: " & txt, vbCritical, TITULO
        Exit Sub
    End If

    Dim rqa As String
    rqa = SoDigitosDe(Pergunta("Número da RQA gerada no MXM:", ""))
    If rqa = "" Then Exit Sub

    Dim portador As String, cartao As String
    portador = UCase$(Pergunta("Portador do cartão:", PORTADOR_PADRAO))
    If portador = "" Then Exit Sub
    cartao = SoDigitosDe(Pergunta("Nº do cartão Flash:", CARTAO_PADRAO))
    If cartao = "" Then Exit Sub

    ' --- período de liberação (padrão: dia seguinte ao ETB, por DIAS_LIBERACAO dias)
    Dim dtDe As Date, dtAte As Date, txtEtb As String
    txtEtb = ExtrairDataApos(corpo, "ETB")
    If txtEtb <> "" Then
        dtDe = TextoParaData(txtEtb) + 1
    Else
        dtDe = Date
    End If
    txt = Pergunta("Liberado DE (dd/mm/aaaa):", DataTxt(dtDe))
    If txt = "" Then Exit Sub
    dtDe = TextoParaData(txt)
    txt = Pergunta("Liberado ATÉ (dd/mm/aaaa):", DataTxt(dtDe + DIAS_LIBERACAO))
    If txt = "" Then Exit Sub
    dtAte = TextoParaData(txt)

    ' --- PDF da RQA
    Dim pasta As String, arqRqa As String
    pasta = EscolherPasta("Selecione a pasta onde está o PDF da RQA " & rqa)
    If pasta <> "" Then arqRqa = AcharArquivoRqa(pasta, rqa)
    If arqRqa = "" Then
        If MsgBox("PDF da RQA " & rqa & " não encontrado na pasta." & vbCrLf & vbCrLf & _
                  "Montar o e-mail mesmo assim (você anexa manualmente)?", vbYesNo + vbQuestion, TITULO) = vbNo Then Exit Sub
    End If

    ' --- e-mail (encaminha o pedido da operação, mantendo a planilha anexada)
    Dim f As Outlook.MailItem
    Set f = m.Forward
    If ENVIAR_COMO_OPSFIN Then f.SentOnBehalfOfName = EMAIL_OPSFIN
    f.To = EMAIL_JESSICA
    f.CC = EMAIL_OPSFIN & ";" & EMAIL_CONTAS
    f.Subject = "OPS SHP - SOLICITAÇÃO DE RECARGA FLASH - FLASH " & portador & " - NR " & cartao & _
                " - " & navio & " - " & viagem & " - " & BRL(vRecarga)
    If arqRqa <> "" Then f.Attachments.Add arqRqa

    Dim html As String
    html = "<div style=""" & FONTE & """>" & _
           "<p>Jessica/" & Esc(NOME_REMETENTE) & ", " & Saudacao() & "!</p>" & _
           "<p>Segue em anexo a <i>RQA " & rqa & "</i> de carga para o cartão FLASH nº " & cartao & _
           ", referente ao <b>" & Esc(referencia) & "</b> do <b>" & Esc(navio) & "</b> (viagem <b>" & viagem & "</b>).</p>" & _
           "<table style=""border-collapse:collapse;" & FONTE & """>" & _
           Linha2("Portador do cartão", portador) & _
           Linha2("Nº do cartão", cartao) & _
           Linha2("Valor de recarga", BRL(vRecarga)) & _
           Linha2("Liberado", "de " & DataTxt(dtDe) & " até " & DataTxt(dtAte)) & _
           "</table><p>Agradeço.</p></div>"

    f.Display
    InserirNoTopo f, html

    GravarLog Array(AgoraTxt(), "SOLICITACAO", viagem, navio, referencia, rqa, portador, cartao, _
                    NumTxt(vRecarga), "", "", "", "", "")
End Sub


'==============================================================================
' ETAPA 2 - PRESTAÇÃO DE CONTAS (envio das DANFEs + POs)
'==============================================================================
Public Sub Flash2_PrestarContasDanfes()
    Dim m As Outlook.MailItem
    Set m = ItemSelecionado()
    If m Is Nothing Then
        MsgBox "Selecione (um clique) o e-mail 'SOLICITAÇÃO DE RECARGA FLASH' desta recarga e rode de novo.", vbExclamation, TITULO
        Exit Sub
    End If

    Dim assunto As String
    assunto = LimparAssunto(m.Subject)
    If InStr(1, assunto, "RECARGA FLASH", vbTextCompare) = 0 Then
        If MsgBox("O e-mail selecionado não parece ser uma SOLICITAÇÃO DE RECARGA FLASH." & vbCrLf & _
                  "Continuar mesmo assim?", vbYesNo + vbQuestion, TITULO) = vbNo Then Exit Sub
    End If

    Dim viagem As String, navio As String, txt As String, vRecarga As Double
    viagem = UCase$(Pergunta("Viagem:", ExtrairViagem(assunto)))
    If viagem = "" Then Exit Sub
    navio = ExtrairNavio(assunto)
    If navio = "" Then navio = NavioPorViagem(viagem)
    txt = Pergunta("Valor da recarga (R$):", ExtrairNumeroApos(assunto, "R$"))
    If txt = "" Then Exit Sub
    vRecarga = ParaNumero(txt)

    Dim pasta As String
    pasta = EscolherPasta("Selecione a pasta com as DANFEs e POs desta recarga (" & viagem & " - " & BRL(vRecarga) & ")")
    If pasta = "" Then Exit Sub

    ' --- leitura da pasta
    Dim danfes As New Collection, pos As New Collection, ignorados As String
    LerPasta pasta, danfes, pos, ignorados
    If danfes.Count = 0 Then
        MsgBox "Nenhuma DANFE encontrada em:" & vbCrLf & pasta & vbCrLf & vbCrLf & _
               "O nome do arquivo precisa conter a palavra DANFE.", vbExclamation, TITULO
        Exit Sub
    End If

    ' --- conferência
    Dim problemas As String, total As Double, qtd As Long, lista As String, quando As String
    Dim d As Variant, p As Variant
    For Each d In danfes
        total = total + d(3)
        lista = POsDaDanfe(d(0), pos, qtd)
        If qtd = 0 Then problemas = problemas & "- DANFE " & d(0) & " (" & d(1) & ") está SEM PO." & vbCrLf
        If qtd > 1 Then problemas = problemas & "- DANFE " & d(0) & " tem " & qtd & " POs: " & lista & vbCrLf
        If d(3) = 0 Then problemas = problemas & "- DANFE " & d(0) & " sem valor." & vbCrLf
        If d(5) <> "" And d(5) <> viagem Then problemas = problemas & "- DANFE " & d(0) & " é da viagem " & d(5) & "." & vbCrLf
        quando = JaPrestada(viagem, d(0))
        If quando <> "" Then problemas = problemas & "- DANFE " & d(0) & " já foi prestada em " & quando & "." & vbCrLf
    Next
    For Each p In pos
        If Not DanfeExiste(p(1), danfes) Then
            problemas = problemas & "- PO " & p(0) & " cita a DANFE " & p(1) & ", que não está na pasta." & vbCrLf
        End If
    Next
    If ignorados <> "" Then problemas = problemas & "- Fora do padrão (NÃO anexados): " & ignorados & vbCrLf

    Dim saldo As Double, resumo As String
    saldo = vRecarga - total
    resumo = "Viagem: " & viagem & "   Navio: " & navio & vbCrLf & _
             "DANFEs: " & danfes.Count & "   POs: " & pos.Count & vbCrLf & vbCrLf & _
             "Recarga:        " & BRL(vRecarga) & vbCrLf & _
             "Total DANFEs:  " & BRL(total) & vbCrLf & _
             "Saldo cartão:  " & BRL(saldo) & vbCrLf

    If problemas <> "" Then
        If Len(problemas) > 700 Then problemas = Left$(problemas, 700) & vbCrLf & "(...)"
        If MsgBox(resumo & vbCrLf & "ATENÇÃO:" & vbCrLf & problemas & vbCrLf & _
                  "Montar o e-mail mesmo assim?", vbYesNo + vbExclamation, TITULO & " - conferência") = vbNo Then Exit Sub
    Else
        If MsgBox(resumo & vbCrLf & "Conferência OK. Montar o e-mail?", vbYesNo + vbInformation, _
                  TITULO & " - conferência") = vbNo Then Exit Sub
    End If

    ' --- e-mail (encaminha a solicitação de recarga)
    Dim f As Outlook.MailItem
    Set f = m.Forward
    If ENVIAR_COMO_OPSFIN Then f.SentOnBehalfOfName = EMAIL_OPSFIN
    f.To = EMAIL_JESSICA & ";" & EMAIL_PROTOCOLO & ";" & EMAIL_CONTAS & ";" & EMAIL_WILL & ";" & EMAIL_SANCHEZ
    f.CC = EMAIL_OPSFIN
    For Each d In danfes
        f.Attachments.Add CStr(d(4))
    Next
    For Each p In pos
        f.Attachments.Add CStr(p(2))
    Next

    Dim linhas As String, estiloSaldo As String
    For Each d In danfes
        linhas = linhas & "<tr>" & Td(CStr(d(0))) & Td(Esc(CStr(d(1)))) & Td(CStr(d(2))) & _
                 TdR(BRL(CDbl(d(3)))) & Td(POsDaDanfe(d(0), pos, qtd)) & "</tr>"
    Next
    If saldo < 0 Then estiloSaldo = "color:#C00000;" Else estiloSaldo = ""

    Dim html As String
    html = "<div style=""" & FONTE & """>" & _
           "<p><b>Protocolo Fiscal</b>, " & Saudacao() & ".</p>" & _
           "<p>Seguem em anexo as POs para atendimento.</p>" & _
           "<p>----- / -----<br><b>Contas a Pagar</b>, para ciência.</p>" & _
           "<p>----- / -----<br><b>Willyanson / Luiz Sanchez</b>, seguem em anexo as DANFEs relacionadas ao rancho da viagem <b>" & _
           viagem & "</b> (" & Esc(navio) & "), referentes à recarga Flash de <b>" & BRL(vRecarga) & "</b>.</p>" & _
           "<table style=""border-collapse:collapse;" & FONTE & """>" & _
           "<tr>" & Th("DANFE") & Th("Fornecedor") & Th("Data") & Th("Valor") & Th("PO") & "</tr>" & _
           linhas & _
           LinhaTotal("Total das DANFEs (" & danfes.Count & ")", BRL(total), "") & _
           LinhaTotal("Valor da recarga", BRL(vRecarga), "") & _
           LinhaTotal("Saldo no cartão", BRL(saldo), estiloSaldo) & _
           "</table><p>Agradeço.</p></div>"

    f.Display
    InserirNoTopo f, html

    ' --- log (registrado ao montar o e-mail)
    For Each d In danfes
        GravarLog Array(AgoraTxt(), "PRESTACAO", viagem, navio, "", "", "", "", NumTxt(vRecarga), _
                        CStr(d(0)), CStr(d(1)), CStr(d(2)), NumTxt(CDbl(d(3))), POsDaDanfe(d(0), pos, qtd))
    Next
End Sub


'==============================================================================
' LEITURA DOS ARQUIVOS
'==============================================================================
' DANFE: "ACR26017 - Assai - DANFE 92811 - R$7.242,43 - 04.09.pdf"
'        -> Array(nº DANFE, fornecedor, data, valor, caminho, viagem)
' PO:    "PO035620 - OPS SHP - AMAZON COURAGE - @ALUMAR - ACR26017 -DANFE 92811 - RANCHO.pdf"
'        -> Array(nº PO, nº DANFE, caminho)
Private Sub LerPasta(ByVal pasta As String, danfes As Collection, pos As Collection, ByRef ignorados As String)
    Dim fso As Object, arq As Object, nome As String, base As String, ext As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    For Each arq In fso.GetFolder(pasta).Files
        nome = arq.Name
        ext = LCase$(fso.GetExtensionName(nome))
        base = fso.GetBaseName(nome)
        If Left$(nome, 1) = "~" Or LCase$(nome) = LCase$(ARQ_LOG) Then
            ' temporários / log: ignora
        ElseIf ext <> "pdf" Then
            ignorados = ignorados & nome & "; "
        ElseIf EhArquivoPO(base) Then
            pos.Add Array(NumeroApos(base, "PO"), TirarZeros(NumeroApos(base, "DANFE")), arq.Path)
        ElseIf InStr(1, base, "DANFE", vbTextCompare) > 0 Then
            danfes.Add LerDanfe(base, arq.Path)
        ElseIf InStr(1, base, "RQA", vbTextCompare) > 0 Then
            ' a RQA já está no e-mail original
        Else
            ignorados = ignorados & nome & "; "
        End If
    Next
End Sub

Private Function LerDanfe(ByVal base As String, ByVal caminho As String) As Variant
    Dim partes() As String, forn As String, dt As String, valor As Double, ultima As String
    partes = Split(base, " - ")
    If UBound(partes) >= 1 Then forn = Trim$(partes(1))
    If InStr(1, forn, "DANFE", vbTextCompare) > 0 Or InStr(forn, "R$") > 0 Then forn = ""
    ultima = Trim$(partes(UBound(partes)))
    If ultima Like "##.##" Or ultima Like "##.##.####" Or ultima Like "##/##" Then dt = Replace(ultima, ".", "/")
    valor = ParaNumero(ExtrairNumeroApos(base, "R$"))
    If valor = 0 Then
        valor = ParaNumero(Pergunta("O valor não está no nome do arquivo:" & vbCrLf & base & vbCrLf & vbCrLf & _
                                    "Informe o valor da DANFE:", ""))
    End If
    LerDanfe = Array(TirarZeros(NumeroApos(base, "DANFE")), forn, dt, valor, caminho, ExtrairViagem(base))
End Function

Private Function EhArquivoPO(ByVal base As String) As Boolean
    Dim s As String, c As String
    s = UCase$(Trim$(base))
    If Left$(s, 2) <> "PO" Then Exit Function
    c = Mid$(s, 3, 1)
    EhArquivoPO = (c = " " Or c Like "#")
End Function

Private Function POsDaDanfe(ByVal numDanfe As Variant, pos As Collection, ByRef qtd As Long) As String
    Dim p As Variant, r As String
    qtd = 0
    For Each p In pos
        If CStr(p(1)) = CStr(numDanfe) Then
            qtd = qtd + 1
            If r <> "" Then r = r & ", "
            r = r & p(0)
        End If
    Next
    POsDaDanfe = r
End Function

Private Function DanfeExiste(ByVal numDanfe As Variant, danfes As Collection) As Boolean
    Dim d As Variant
    For Each d In danfes
        If CStr(d(0)) = CStr(numDanfe) Then DanfeExiste = True: Exit Function
    Next
End Function

Private Function AcharArquivoRqa(ByVal pasta As String, ByVal rqa As String) As String
    Dim fso As Object, arq As Object, s As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    For Each arq In fso.GetFolder(pasta).Files
        s = UCase$(Replace(arq.Name, " ", ""))
        If InStr(s, "RQA" & rqa) > 0 Then AcharArquivoRqa = arq.Path: Exit Function
    Next
End Function


'==============================================================================
' LOG (FLASH_LOG.csv)
'==============================================================================
Private Function CaminhoLog() As String
    CaminhoLog = PASTA_RAIZ & "\" & ARQ_LOG
End Function

Private Sub GravarLog(campos As Variant)
    On Error GoTo falha
    Dim fso As Object, ts As Object, novo As Boolean, i As Long, linha As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FolderExists(PASTA_RAIZ) Then fso.CreateFolder PASTA_RAIZ
    novo = Not fso.FileExists(CaminhoLog())
    Set ts = fso.OpenTextFile(CaminhoLog(), 8, True)
    If novo Then ts.WriteLine "DataHora;Etapa;Viagem;Navio;Referencia;RQA;Portador;Cartao;ValorRecarga;DANFE;Fornecedor;DataDANFE;ValorDANFE;PO"
    For i = LBound(campos) To UBound(campos)
        If i > LBound(campos) Then linha = linha & ";"
        linha = linha & Replace(CStr(campos(i)), ";", ",")
    Next
    ts.WriteLine linha
    ts.Close
    Exit Sub
falha:
    MsgBox "Não consegui gravar o log em " & CaminhoLog() & vbCrLf & Err.Description, vbExclamation, TITULO
End Sub

' Retorna a data em que a DANFE já foi prestada nesta viagem (ou "")
Private Function JaPrestada(ByVal viagem As String, ByVal numDanfe As Variant) As String
    On Error GoTo fim
    Dim fso As Object, ts As Object, c() As String
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Not fso.FileExists(CaminhoLog()) Then Exit Function
    Set ts = fso.OpenTextFile(CaminhoLog(), 1)
    Do While Not ts.AtEndOfStream
        c = Split(ts.ReadLine, ";")
        If UBound(c) >= 9 Then
            If c(1) = "PRESTACAO" And c(2) = viagem And c(9) = CStr(numDanfe) Then
                JaPrestada = Left$(c(0), 10)
                Exit Do
            End If
        End If
    Loop
    ts.Close
fim:
End Function


'==============================================================================
' OUTLOOK / INTERFACE
'==============================================================================
Private Function ItemSelecionado() As Outlook.MailItem
    On Error Resume Next
    If TypeName(Application.ActiveWindow) = "Inspector" Then
        If TypeOf Application.ActiveInspector.CurrentItem Is Outlook.MailItem Then
            Set ItemSelecionado = Application.ActiveInspector.CurrentItem
        End If
        Exit Function
    End If
    Dim sel As Outlook.Selection
    Set sel = Application.ActiveExplorer.Selection
    If sel.Count = 1 Then
        If TypeOf sel.Item(1) Is Outlook.MailItem Then Set ItemSelecionado = sel.Item(1)
    End If
End Function

Private Function EscolherPasta(ByVal msg As String) As String
    On Error Resume Next
    Dim sh As Object, pst As Object, fso As Object
    Set sh = CreateObject("Shell.Application")
    Set fso = CreateObject("Scripting.FileSystemObject")
    If fso.FolderExists(PASTA_RAIZ) Then
        Set pst = sh.BrowseForFolder(0, msg, 0, PASTA_RAIZ)
    Else
        Set pst = sh.BrowseForFolder(0, msg, 0, 17)   ' "Este Computador"
    End If
    If Not pst Is Nothing Then EscolherPasta = pst.Self.Path
End Function

Private Function Pergunta(ByVal texto As String, ByVal padrao As String) As String
    Pergunta = Trim$(InputBox(texto, TITULO, padrao))
End Function

Private Sub InserirNoTopo(f As Outlook.MailItem, ByVal html As String)
    Dim b As String, p As Long, q As Long
    b = f.HTMLBody
    p = InStr(1, b, "<body", vbTextCompare)
    If p > 0 Then
        q = InStr(p, b, ">")
        f.HTMLBody = Left$(b, q) & html & Mid$(b, q + 1)
    Else
        f.HTMLBody = html & b
    End If
End Sub

Private Function Saudacao() As String
    Select Case Hour(Now)
        Case Is < 12: Saudacao = "bom dia"
        Case Is < 18: Saudacao = "boa tarde"
        Case Else: Saudacao = "boa noite"
    End Select
End Function


'==============================================================================
' HTML
'==============================================================================
Private Function Esc(ByVal s As String) As String
    s = Replace(s, "&", "&amp;")
    s = Replace(s, "<", "&lt;")
    Esc = Replace(s, ">", "&gt;")
End Function

Private Function Th(ByVal s As String) As String
    Th = "<td style=""border:1px solid #BFBFBF;background:#F1F5F9;padding:4px 10px""><b>" & s & "</b></td>"
End Function

Private Function Td(ByVal s As String) As String
    Td = "<td style=""border:1px solid #BFBFBF;padding:4px 10px"">" & s & "</td>"
End Function

Private Function TdR(ByVal s As String) As String
    TdR = "<td style=""border:1px solid #BFBFBF;padding:4px 10px;text-align:right;white-space:nowrap"">" & s & "</td>"
End Function

Private Function Linha2(ByVal rotulo As String, ByVal valor As String) As String
    Linha2 = "<tr><td style=""padding:2px 16px 2px 0"">" & rotulo & ":</td><td style=""padding:2px 0""><b>" & _
             Esc(valor) & "</b></td></tr>"
End Function

Private Function LinhaTotal(ByVal rotulo As String, ByVal valor As String, ByVal estilo As String) As String
    LinhaTotal = "<tr><td colspan=""3"" style=""border:1px solid #BFBFBF;padding:4px 10px;text-align:right""><b>" & rotulo & _
                 "</b></td><td style=""border:1px solid #BFBFBF;padding:4px 10px;text-align:right;white-space:nowrap;" & estilo & _
                 """><b>" & valor & "</b></td><td style=""border:1px solid #BFBFBF""></td></tr>"
End Function


'==============================================================================
' TEXTO / NÚMEROS / DATAS
'==============================================================================
Private Function LimparAssunto(ByVal s As String) As String
    Dim prefixos As Variant, p As Variant, mudou As Boolean
    prefixos = Array("ENC:", "RES:", "RE:", "FW:", "FWD:", "TR:")
    Do
        mudou = False
        s = Trim$(s)
        For Each p In prefixos
            If UCase$(Left$(s, Len(p))) = p Then
                s = Mid$(s, Len(p) + 1)
                mudou = True
            End If
        Next
    Loop While mudou
    LimparAssunto = Trim$(s)
End Function

' Primeira ocorrência de 3 letras + 5 dígitos (aceita espaço no meio): ACR26017, ACR 26017
Private Function ExtrairViagem(ByVal s As String) As String
    Dim i As Long, j As Long, t As String
    s = UCase$(s)
    For i = 1 To Len(s) - 7
        If EhLetra(Mid$(s, i, 1)) And EhLetra(Mid$(s, i + 1, 1)) And EhLetra(Mid$(s, i + 2, 1)) Then
            If i = 1 Then
                j = i + 3
            ElseIf Not EhLetra(Mid$(s, i - 1, 1)) Then
                j = i + 3
            Else
                j = 0
            End If
            If j > 0 Then
                If Mid$(s, j, 1) = " " Then j = j + 1
                t = Mid$(s, j, 5)
                If t Like "#####" And Not (Mid$(s, j + 5, 1) Like "#") Then
                    ExtrairViagem = Mid$(s, i, 3) & t
                    Exit Function
                End If
            End If
        End If
    Next
End Function

Private Function NavioPorViagem(ByVal viagem As String) As String
    Select Case UCase$(Left$(viagem, 3))
        Case "APN": NavioPorViagem = "AMAZON PIONEER"
        Case "APT", "APF": NavioPorViagem = "AMAZON PATHFINDER"
        Case "ACM": NavioPorViagem = "AMAZON COMMANDER"
        Case "ACR": NavioPorViagem = "AMAZON COURAGE"
    End Select
End Function

Private Function ExtrairNavio(ByVal s As String) As String
    Dim p As Long, i As Long, c As String, w As String
    s = UCase$(s)
    p = InStr(s, "AMAZON ")
    If p = 0 Then Exit Function
    For i = p + 7 To Len(s)
        c = Mid$(s, i, 1)
        If Not EhLetra(c) Then Exit For
        w = w & c
    Next
    If w <> "" Then ExtrairNavio = "AMAZON " & w
End Function

Private Function EhLetra(ByVal c As String) As Boolean
    EhLetra = (UCase$(c) Like "[A-Z]")
End Function

Private Function UltimaPalavra(ByVal s As String) As String
    s = Trim$(s)
    UltimaPalavra = Mid$(s, InStrRev(s, " ") + 1)
End Function

' Texto numérico logo após o marcador: "R$ 7.242,43" -> "7.242,43"
Private Function ExtrairNumeroApos(ByVal s As String, ByVal marcador As String) As String
    Dim p As Long, c As String, r As String
    p = InStr(1, s, marcador, vbTextCompare)
    If p = 0 Then Exit Function
    p = p + Len(marcador)
    Do While Mid$(s, p, 1) = " " Or Mid$(s, p, 1) = Chr(160)
        p = p + 1
    Loop
    Do While p <= Len(s)
        c = Mid$(s, p, 1)
        If Not (c Like "#" Or c = "." Or c = ",") Then Exit Do
        r = r & c
        p = p + 1
    Loop
    Do While Len(r) > 0 And (Right$(r, 1) = "." Or Right$(r, 1) = ",")
        r = Left$(r, Len(r) - 1)
    Loop
    ExtrairNumeroApos = r
End Function

' Dígitos logo após o marcador: "PO 035618" -> "035618"; "DANFE Nº 669" -> "669"
Private Function NumeroApos(ByVal s As String, ByVal marcador As String) As String
    Dim p As Long, n As Long, c As String, r As String
    p = InStr(1, s, marcador, vbTextCompare)
    If p = 0 Then Exit Function
    p = p + Len(marcador)
    Do While p <= Len(s) And n < 6
        c = Mid$(s, p, 1)
        If c Like "#" Then Exit Do
        p = p + 1
        n = n + 1
    Loop
    Do While p <= Len(s)
        c = Mid$(s, p, 1)
        If Not (c Like "#") Then Exit Do
        r = r & c
        p = p + 1
    Loop
    NumeroApos = r
End Function

Private Function SoDigitosDe(ByVal s As String) As String
    Dim i As Long, c As String
    For i = 1 To Len(s)
        c = Mid$(s, i, 1)
        If c Like "#" Then SoDigitosDe = SoDigitosDe & c
    Next
End Function

Private Function TirarZeros(ByVal s As String) As String
    Do While Len(s) > 1 And Left$(s, 1) = "0"
        s = Mid$(s, 2)
    Loop
    TirarZeros = s
End Function

' "25.000,00" / "25000" / "25000,5" -> Double (independe da configuração regional)
Private Function ParaNumero(ByVal s As String) As Double
    s = Trim$(Replace(Replace(s, "R$", ""), " ", ""))
    If s = "" Then Exit Function
    s = Replace(s, ".", "")
    s = Replace(s, ",", ".")
    ParaNumero = Val(s)
End Function

' 7242.43 -> "R$ 7.242,43" (independe da configuração regional)
Private Function BRL(ByVal v As Double) As String
    BRL = IIf(v < 0, "-", "") & "R$ " & NumTxt(Abs(v))
End Function

Private Function NumTxt(ByVal v As Double) As String
    Dim s As String, inteiro As String, dec As String, r As String, neg As Boolean
    neg = (v < 0)
    s = Replace(Format$(Abs(v), "0.00"), ",", ".")
    inteiro = Split(s, ".")(0)
    dec = Split(s, ".")(1)
    Do While Len(inteiro) > 3
        r = "." & Right$(inteiro, 3) & r
        inteiro = Left$(inteiro, Len(inteiro) - 3)
    Loop
    NumTxt = IIf(neg, "-", "") & inteiro & r & "," & dec
End Function

' Primeira data dd/mm/aaaa após o marcador
Private Function ExtrairDataApos(ByVal s As String, ByVal marcador As String) As String
    Dim p As Long, i As Long
    p = InStr(1, s, marcador, vbTextCompare)
    If p = 0 Then Exit Function
    For i = p To Len(s) - 9
        If Mid$(s, i, 10) Like "##/##/####" Then
            ExtrairDataApos = Mid$(s, i, 10)
            Exit Function
        End If
    Next
End Function

Private Function TextoParaData(ByVal t As String) As Date
    On Error GoTo erro
    Dim c() As String, ano As Long
    c = Split(Trim$(t), "/")
    If UBound(c) >= 2 Then ano = CLng(c(2)) Else ano = Year(Date)
    If ano < 100 Then ano = ano + 2000
    TextoParaData = DateSerial(ano, CLng(c(1)), CLng(c(0)))
    Exit Function
erro:
    TextoParaData = Date
End Function

Private Function DataTxt(ByVal d As Date) As String
    DataTxt = Right$("0" & Day(d), 2) & "/" & Right$("0" & Month(d), 2) & "/" & Year(d)
End Function

Private Function AgoraTxt() As String
    AgoraTxt = DataTxt(Date) & " " & Right$("0" & Hour(Now), 2) & ":" & Right$("0" & Minute(Now), 2)
End Function
