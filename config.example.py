"""Exemplo de config para o projeto de agendamento.
Copie este arquivo como config.py e preencha os valores reais localmente.
Nunca versionar config.py com senhas ou credenciais reais.
"""

# Google API
GOOGLE_CREDENTIALS_FILE = "credentials.json"
GOOGLE_SHEET_ID         = "SEU_SHEET_ID_AQUI"
SHEET_WORKSHEET_NAME    = "Respostas ao formulário 1"

COLUMN_MAP = {
    "timestamp":    "Carimbo de data/hora",
    "solicitation": "1- Solicitação",
    "lab":          "2- Laboratório",
    "period":       "3- Período",
    "num_students": "4- Caso seja Laboratório de Informática, indicar o número de alunos da turma.",
    "professor":    "5- Professor responsável",
    "discipline":   "6- Diciplina",
    "date":         "7- Data da Reserva\n(Para aulas mensais e inicio das aulas semanais)",
    "weekday":      "8- No caso de aulas semanais, selecionar o dia da semana que será utilizado\n(Para reserva de um único dia, deixar esse campo em branco)",
    "time_slot":    "9- Horário da reserva.",
    "topic":        "10- Tema da Aula prática",
    "materials":    "12- Listar os materiais que  serão utilizados na aula\nNo e-mail de confirmação serão informados os materiais disponíveis. \nCaso o laboratório não tenha o material, ele entrará para a próxima lista de compras.",
    "email":        "Endereço de e-mail",
}

ADMIN_EMAIL = "seu_admin@exemplo.com"
ADMIN_NAME  = "Apoio dos Laboratorios"

SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "seu_email@gmail.com"
SMTP_PASSWORD = "sua_senha_de_app_aqui"

DB_PATH = "agendamentos.db"
MIN_BUSINESS_DAYS_AHEAD = 7
HOLIDAYS = [
    "01-01", "04-18", "04-21", "05-01",
    "09-07", "10-12", "11-02", "11-15", "12-25",
]
CHECK_INTERVAL_MINUTES = 5
VALID_LABS = [
    "Laboratorio de Automacao e Eletroeletronica",
    "Laboratorio de Eletrotecnica",
    "Laboratorio de Multidisciplinar (Fisica / Quimica)",
    "Laboratorio de Mecanica / Solda e Processos",
    "Laboratorio de Materiais / Fluidos e Termicos",
    "Laboratorio de Desenho 1",
    "Laboratorio de Desenho 2",
    "Laboratorio de Desenho 3 - Sala 06 (EaD)",
    "Laboratorio Nucleo de Arquitetura (Maquetaria, Conforto e Topografia)",
    "Laboratorio de Construcao Civil e Solos",
    "Laboratorio de Informatica",
    "Ncom (Tv)",
    "Ncom (Radio)",
    "Ncom (Design)",
    "Ncom (Fotografia)",
]
WEEKDAY_MAP = {
    "Toda segunda-feira": 0,
    "Toda terca-feira":   1,
    "Toda quarta-feira":  2,
    "Toda quinta-feira":  3,
    "Toda sexta-feira":   4,
}
