# Voice-Activated Equipment Rental System

A modern, voice-enabled equipment rental management system designed for construction companies and equipment rental businesses. This system allows users to browse, rent, and manage construction equipment through both traditional interfaces and voice commands.

## 🎯 Project Overview

The Voice-Activated Equipment Rental System streamlines the equipment rental process by providing an intuitive interface with voice command capabilities. Users can search for equipment, check availability, make reservations, and manage rentals using natural language voice commands or traditional input methods.

## ✨ Features

### Core Functionality
- **Equipment Catalog Management**: Browse and search through available construction equipment
- **Voice-Activated Search**: Find equipment using natural voice commands
- **Real-time Availability**: Check equipment availability in real-time
- **Rental Management**: Create, modify, and track equipment rentals
- **User Authentication**: Secure user accounts and rental history
- **Reservation System**: Book equipment in advance
- **Pricing Calculator**: Automatic calculation of rental costs based on duration

### Voice Commands
- "Show me available excavators"
- "Rent a backhoe for 3 days"
- "What equipment is available tomorrow?"
- "Check my rental history"
- "Cancel my reservation"

## 🛠 Tech Stack

### Frontend
- **Framework**: React.js / Vue.js (TBD)
- **Voice Recognition**: Web Speech API / Google Cloud Speech-to-Text
- **UI Components**: Material-UI / Tailwind CSS
- **State Management**: Redux / Context API

### Backend
- **Server**: Node.js with Express / Python with Flask (TBD)
- **Database**: PostgreSQL / MongoDB (TBD)
- **Authentication**: JWT / OAuth 2.0
- **API**: RESTful API / GraphQL

### Additional Services
- **Voice Processing**: Natural Language Processing (NLP) for command interpretation
- **Payment Integration**: Stripe / PayPal (TBD)
- **Notifications**: Email/SMS notifications for bookings

## 📋 Prerequisites

Before running this project, ensure you have:
- Node.js (v14 or higher) / Python (v3.8 or higher)
- npm or yarn package manager
- Database system (PostgreSQL/MongoDB)
- Modern web browser with microphone access

## 🚀 Installation

```bash
# Clone the repository
git clone https://github.com/scoutts2/Voice-Activated-Equipment-Rental-System.git

# Navigate to project directory
cd Voice-Activated-Equipment-Rental-System

# Install dependencies
npm install
# or
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
npm run db:setup
# or
python manage.py db:setup

# Start the development server
npm run dev
# or
python app.py
```

## 📁 Project Structure

```
Voice-Activated-Equipment-Rental-System/
├── client/                 # Frontend application
│   ├── src/
│   │   ├── components/    # React/Vue components
│   │   ├── services/      # API services
│   │   ├── utils/         # Utility functions
│   │   └── voice/         # Voice recognition modules
│   └── public/            # Static assets
├── server/                # Backend application
│   ├── controllers/       # Route controllers
│   ├── models/            # Database models
│   ├── routes/            # API routes
│   ├── middleware/        # Custom middleware
│   └── services/          # Business logic
├── database/              # Database schemas and migrations
├── docs/                  # Additional documentation
├── tests/                 # Test files
└── README.md
```

## 🎮 Usage

### Web Interface
1. Navigate to `http://localhost:3000` in your browser
2. Create an account or log in
3. Browse the equipment catalog
4. Select equipment and specify rental duration
5. Complete the booking process

### Voice Commands
1. Click the microphone icon in the interface
2. Speak your command clearly
3. The system will process your request and respond accordingly

### Example Voice Interactions
```
User: "Show me available bulldozers"
System: "I found 3 bulldozers available. Would you like to see details?"

User: "Yes, show me the first one"
System: "Caterpillar D6T Bulldozer, $500 per day. Would you like to rent it?"

User: "Book it for 5 days starting tomorrow"
System: "Booking confirmed! Total cost: $2,500. Confirmation sent to your email."
```

## 🧪 Testing

```bash
# Run all tests
npm test

# Run with coverage
npm run test:coverage

# Run specific test suite
npm test -- --grep "voice commands"
```

## 🔐 Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Server Configuration
PORT=3000
NODE_ENV=development

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=equipment_rental
DB_USER=your_username
DB_PASSWORD=your_password

# Authentication
JWT_SECRET=your_jwt_secret
JWT_EXPIRE=24h

# Voice API Keys
SPEECH_API_KEY=your_speech_api_key

# Payment Gateway
STRIPE_SECRET_KEY=your_stripe_key
```

## 📊 Database Schema

### Main Tables
- **Users**: User accounts and authentication
- **Equipment**: Equipment catalog and specifications
- **Rentals**: Active and historical rentals
- **Reservations**: Future bookings
- **Payments**: Transaction records

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👥 Authors

- **Samuel Coutts** - [scoutts2](https://github.com/scoutts2)

## 🙏 Acknowledgments

- Web Speech API documentation
- Construction equipment rental industry standards
- Open source community

## 📞 Contact

For questions or support, please open an issue on GitHub or contact the maintainers.

## 🗺 Roadmap

### Phase 1: Core Features (MVP)
- [ ] Basic equipment catalog
- [ ] User authentication
- [ ] Simple rental system
- [ ] Voice search functionality

### Phase 2: Enhanced Features
- [ ] Advanced voice commands
- [ ] Payment integration
- [ ] Mobile app
- [ ] Real-time notifications

### Phase 3: Advanced Features
- [ ] AI-powered recommendations
- [ ] Multi-location support
- [ ] Analytics dashboard
- [ ] Integration with external systems

## 📈 Version History

- **0.1.0** - Initial project setup and documentation

---

**Built with ❤️ for the construction industry**

